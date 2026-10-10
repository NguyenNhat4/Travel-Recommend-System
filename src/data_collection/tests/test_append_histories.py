"""Append batches: identity isolation, tamper detection and real DB rollback/idempotence."""
import copy
import os
import unittest
from datetime import date

import psycopg

from data_collection.seed.append_histories import apply, digest, validate


def artifact():
    prefix = 'VPX:test-batch:'
    profile = dict(cdp_user_id=prefix+'VP0000005', lifecycle_stage='new', days_since_last_booking=None,
                   lifetime_order_count=0, vinclub_tier='Member', purchased_verticals=[], home_city='Hà Nội',
                   last_destination=None, email_optin=True, sms_optin=True, push_optin=True,
                   created_at='2026-10-01T00:00:00Z', updated_at='2026-10-02T00:00:00Z')
    event = dict(cdp_user_id=profile['cdp_user_id'], event_name='product_view', timestamp='2026-10-02T00:00:00Z',
                 product_id='00000000-0000-0000-0000-000000000001', taxonomy='hotel', event_group_id=None,
                 quantity=None, unit_price=None, using_date=None)
    p = dict(format=1, synthetic=True, batch='test-batch', prefix=prefix, as_of='2026-10-05', seed=42,
             catalog_sha256='test', profiles=[profile], events=[event])
    return dict(payload=p, sha256=digest(p))


class ValidationTests(unittest.TestCase):
    def test_tampered_payload(self):
        a = artifact()
        a['payload']['seed'] = 1
        with self.assertRaises(ValueError): validate(a)

    def test_old_user_cannot_be_appended(self):
        a = artifact()
        a['payload']['profiles'][0]['cdp_user_id'] = 'VP0000001'
        a['sha256'] = digest(a['payload'])
        with self.assertRaises(ValueError): validate(a)

    def test_foreign_event_group(self):
        a = artifact()
        a['payload']['events'][0]['event_group_id'] = 'old-group'
        a['sha256'] = digest(a['payload'])
        with self.assertRaises(ValueError): validate(a)


@unittest.skipUnless(os.getenv('APPEND_TEST_DATABASE_URL'), 'requires a disposable empty database')
class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.conn = psycopg.connect(os.environ['APPEND_TEST_DATABASE_URL'])
        # Isolated disposable database only. No DROP/DELETE; setup rolled back after each test.
        self.conn.execute('CREATE SCHEMA cdp')
        self.conn.execute('CREATE TABLE cdp.products(product_id uuid primary key)')
        self.conn.execute('''CREATE TABLE cdp.profiles(cdp_user_id text primary key, lifecycle_stage text,
          days_since_last_booking int, lifetime_order_count int, vinclub_tier text, purchased_verticals text[],
          home_city text, last_destination text, email_optin bool, sms_optin bool, push_optin bool,
          created_at timestamptz, updated_at timestamptz)''')
        self.conn.execute('''CREATE TABLE cdp.events(event_id bigserial primary key, cdp_user_id text references cdp.profiles,
          event_name text, timestamp timestamptz, product_id uuid, taxonomy text, event_group_id text,
          quantity int, unit_price numeric, using_date date)''')
        self.conn.execute("INSERT INTO cdp.products VALUES ('00000000-0000-0000-0000-000000000001')")
        self.conn.execute("INSERT INTO cdp.profiles(cdp_user_id) VALUES ('VP0000001')")
        self.conn.execute("INSERT INTO cdp.events(cdp_user_id,event_name) VALUES ('VP0000001','search')")

    def tearDown(self):
        self.conn.rollback()
        self.conn.close()

    def clear_temp(self):
        self.conn.execute('DROP TABLE append_profiles, append_events')

    def test_idempotent_and_old_data_unchanged(self):
        before = self.conn.execute("SELECT row_to_json(p) FROM cdp.profiles p WHERE cdp_user_id='VP0000001'").fetchone()
        a = artifact()
        self.assertEqual(apply(self.conn,a)['status'],'inserted')
        self.clear_temp()
        self.assertEqual(apply(self.conn,a)['status'],'already_applied')
        self.assertEqual(self.conn.execute('SELECT count(*) FROM cdp.events').fetchone()[0],2)
        self.assertEqual(before,self.conn.execute("SELECT row_to_json(p) FROM cdp.profiles p WHERE cdp_user_id='VP0000001'").fetchone())

    def test_missing_product_rolls_back(self):
        a=artifact()
        a['payload']['events'][0]['product_id']='00000000-0000-0000-0000-000000000002'
        a['sha256']=digest(a['payload'])
        with self.assertRaises(ValueError), self.conn.transaction(): apply(self.conn,a)
        self.assertEqual(self.conn.execute('SELECT count(*) FROM cdp.profiles').fetchone()[0],1)

    def test_changed_persisted_batch_rejected(self):
        a=artifact()
        apply(self.conn,a)
        self.clear_temp()
        self.conn.execute("UPDATE cdp.events SET quantity=2 WHERE starts_with(cdp_user_id,'VPX:')")
        with self.assertRaises(ValueError), self.conn.transaction(): apply(self.conn,a)

class GenerationTests(unittest.TestCase):
    def test_valid_products_persona_isolation_and_derived_orders(self):
        from unittest.mock import patch
        from collections import defaultdict
        from data_collection.seed import config as C
        from data_collection.seed.append_histories import build
        from data_collection.tests.test_seed_histories import make_catalog
        catalog=make_catalog()
        with patch.dict(C.PROFILES['append-v1'], DEFAULT_USERS=604):
            a=build(catalog,batch='generated-test',as_of=date(2026,9,20),seed=7)
        p=validate(a)
        self.assertEqual(len(p['profiles']),600)
        known={r['productId'] for r in catalog}
        groups=defaultdict(set)
        for e in p['events']:
            self.assertTrue(e['product_id'] is None or e['product_id'] in known)
            self.assertNotIn(e['cdp_user_id'].split(':')[-1],{x[0] for x in C.PERSONAS})
            if e['event_name']=='purchase':
                self.assertIsNotNone(e['event_group_id'])
                groups[e['cdp_user_id']].add(e['event_group_id'])
        for profile in p['profiles']:
            self.assertEqual(profile['lifetime_order_count'],len(groups[profile['cdp_user_id']]))
        self.assertEqual(C.MESSY_PURCHASE_BAD_PRODUCT,0.02)
