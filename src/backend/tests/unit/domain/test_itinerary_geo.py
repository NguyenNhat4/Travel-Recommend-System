"""Luật khoảng cách của lịch trình (AC-AGT-04, chốt 2026-10-07)."""
import math
import unittest

from src.backend.app.domain.itinerary.geo import band, haversine_km, located, medoid


def place(pid, lat, lng, destination='Huế'):
    return {'productId': pid, 'destination': destination, 'attributes': {'latitude': lat, 'longitude': lng}}


class HaversineTests(unittest.TestCase):
    def test_one_degree_of_latitude_is_about_111_km(self):
        self.assertAlmostEqual(haversine_km((10.0, 106.0), (11.0, 106.0)), 111.19, places=1)

    def test_the_distance_is_symmetric_and_zero_for_the_same_point(self):
        a, b = (16.4637, 107.5909), (16.4460, 107.5600)
        self.assertEqual(haversine_km(a, a), 0)
        self.assertAlmostEqual(haversine_km(a, b), haversine_km(b, a))


class BandTests(unittest.TestCase):
    def test_distances_within_two_km_share_a_band(self):
        self.assertEqual(band(0.3), band(1.9))
        self.assertLess(band(1.9), band(2.1))

    def test_an_unknown_distance_sorts_after_every_known_one(self):
        self.assertEqual(band(None), math.inf)
        self.assertLess(band(500), band(None))


class MedoidTests(unittest.TestCase):
    def test_the_medoid_is_an_input_point_and_ignores_a_far_outlier(self):
        points = {'a': (10.00, 104.00), 'b': (10.01, 104.00), 'c': (10.02, 104.00), 'far': (10.40, 104.00)}
        self.assertEqual(medoid(points), (10.01, 104.00))

    def test_no_point_has_no_medoid(self):
        self.assertIsNone(medoid({}))


class LocatedTests(unittest.TestCase):
    def test_precise_coordinates_are_kept_even_when_many_products_share_them(self):
        products = [place(f'vin{index}', 10.340735, 103.854047, 'Phú Quốc') for index in range(8)]
        self.assertEqual(set(located(products)), {f'vin{index}' for index in range(8)})

    def test_a_low_precision_point_shared_by_five_products_is_a_city_centre(self):
        tours = [place(f'tour{index}', 16.4639, 107.5863) for index in range(5)]
        self.assertEqual(located(tours + [place('citadel', 16.469722, 107.578611)]), {'citadel': (16.469722, 107.578611)})

    def test_a_low_precision_point_shared_by_fewer_than_five_is_kept(self):
        tours = [place(f'tour{index}', 16.4639, 107.5863) for index in range(4)]
        self.assertEqual(len(located(tours)), 4)

    def test_the_shared_count_is_per_destination(self):
        products = [place(f'hue{index}', 16.4639, 107.5863) for index in range(3)]
        products += [place(f'other{index}', 16.4639, 107.5863, 'Đà Nẵng') for index in range(3)]
        self.assertEqual(len(located(products)), 6)

    def test_missing_or_invalid_coordinates_are_not_located(self):
        products = [{'productId': 'none', 'attributes': {}}, place('text', 'abc', 107.5), place('bool', True, 107.5),
                    place('range', 95.0, 107.5)]
        self.assertEqual(located(products), {})


if __name__ == '__main__':
    unittest.main()
