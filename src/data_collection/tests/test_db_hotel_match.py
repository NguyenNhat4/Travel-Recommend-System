"""Nạp DB không tạo khách sạn trùng: khách sạn mới khớp khách sạn nguồn khác đã có trong DB thì gộp vào, và dòng đã gộp không
bị lượt cào bật lại (production 08/10/2026: 20 nhóm Booking + Agoda/Trip, 3 nhóm tin đăng trùng cùng nguồn)."""
from fresh_catalog_db import match_existing_hotels, prepare_rows
from normalise import product_id


def fresh(ref, name='Royal Hotel Saigon', lat=10.7745, lon=106.7040, parent=None, dest='TP. Hồ Chí Minh'):
    attrs = {'level': 'room', 'parentProductId': parent} if parent else {'level': 'property', 'latitude': lat,
                                                                          'longitude': lon}
    return {'productId': product_id(ref), 'name': name, 'taxonomy': 'hotel', 'destination': dest, 'description': 'x',
            'attributes': attrs, 'unitPrice': 100, 'currency': 'VND', 'available': True, 'availableFrom': None,
            'availableTo': None, 'imageUrl': None, 'sourceRef': ref}


def db(ref, name='Royal Hotel Saigon', lat=10.7747, lon=106.7041, dest='TP. Hồ Chí Minh', **attrs):
    return {'product_id': product_id(ref), 'source_ref': ref, 'name': name, 'taxonomy': 'hotel', 'destination': dest,
            'description': 'x', 'attributes': {'level': 'property', 'latitude': lat, 'longitude': lon, **attrs},
            'unit_price': 1, 'currency': 'VND', 'available': True, 'available_from': None, 'available_to': None,
            'image_url': None}


def test_new_agoda_hotel_matching_a_booking_row_is_merged_into_it():
    booking = db('booking:hotel:71001')
    agoda = fresh('agoda:hotel:royal-hotel-saigon:ho-chi-minh-city')
    room = fresh('agoda:hotel:royal-hotel-saigon:ho-chi-minh-city:room:1', parent=agoda['productId'])
    rows, counts = prepare_rows([agoda, room], [booking], set(), '2026-10-08')
    by_ref = {r['source_ref']: r for r in rows}
    hidden = by_ref['agoda:hotel:royal-hotel-saigon:ho-chi-minh-city']
    assert (hidden['available'], hidden['attributes']['mergedInto']) == (False, booking['product_id'])
    assert by_ref['booking:hotel:71001']['attributes']['sameAs'] == ['agoda:hotel:royal-hotel-saigon:ho-chi-minh-city']
    assert by_ref[room['sourceRef']]['attributes']['parentProductId'] == booking['product_id']  # phòng sang dòng giữ
    assert counts['dbMatched'] == 1
    # lượt sau: ref agoda đã nằm trong sameAs của dòng Booking nên khớp thẳng, không tạo dòng mới
    later = [dict(r) for r in rows]
    rows, counts = prepare_rows([agoda], later, set(), '2026-10-09')
    assert counts['new'] == 0 and counts['dbMatched'] == 0


def test_not_merged_when_evidence_is_weak_or_ambiguous():
    cases = {
        'tên khác': ([db('booking:hotel:1', name='Royal Hotel Saigon')], fresh('agoda:hotel:a:hcm', name='Royal Saigon Boutique')),
        'xa hơn 1 km': ([db('booking:hotel:1', lat=10.80)], fresh('agoda:hotel:a:hcm')),
        'dòng DB đã có bản Agoda khác': ([db('booking:hotel:1', sameAs=['agoda:hotel:other:hcm'])], fresh('agoda:hotel:a:hcm')),
        'cùng nguồn': ([db('agoda:hotel:b:hcm')], fresh('agoda:hotel:a:hcm')),
        'căn hộ khác chủ': ([db('booking:hotel:1', name="Căn hộ khách sạn L'azur Cửa Lò")],
                            fresh('agoda:hotel:a:cl', name="Căn hộ khách sạn L'azur Cửa Lò")),
        'khác điểm đến': ([db('booking:hotel:1', dest='Hà Nội')], fresh('agoda:hotel:a:hcm')),
        'hai ứng viên': ([db('booking:hotel:1'), db('trip:hotel:2')], fresh('agoda:hotel:a:hcm')),
    }
    for label, (existing, item) in cases.items():
        assert match_existing_hotels([item], existing, {item['productId']: []}) == {}, label


def test_missing_coordinates_on_one_side_still_matches_identical_name():
    booking = db('booking:hotel:505120', name='Havana Nha Trang Hotel', dest='Nha Trang')
    trip = fresh('trip:hotel:713858', name='Havana Nha Trang Hotel', lat=None, lon=None, dest='Nha Trang')
    assert match_existing_hotels([trip], [booking], {trip['productId']: []}) == {trip['productId']: booking}


def test_merged_duplicate_listing_stays_hidden_when_the_source_still_lists_it():
    keeper = db('booking:hotel:16197629', name='Behomestay', dest='Hải Phòng')
    loser = db('booking:hotel:16347719', name='Behomestay', dest='Hải Phòng', mergedInto=product_id('booking:hotel:16197629'))
    loser['available'] = False
    keeper_fresh = fresh('booking:hotel:16197629', name='Behomestay', dest='Hải Phòng')
    loser_fresh = fresh('booking:hotel:16347719', name='Behomestay', dest='Hải Phòng')
    loser_room = fresh('booking:hotel:16347719:room:1', parent=loser_fresh['productId'], dest='Hải Phòng')
    rows, counts = prepare_rows([keeper_fresh, loser_fresh, loser_room], [keeper, loser], set(), '2026-10-09')
    by_ref = {r['source_ref']: r for r in rows}
    assert by_ref['booking:hotel:16197629']['available'] is True
    assert by_ref['booking:hotel:16347719']['available'] is False  # trước đây lượt cào bật lại tin trùng
    assert by_ref['booking:hotel:16347719:room:1']['available'] is False
    assert counts['keptMerged'] == 1
