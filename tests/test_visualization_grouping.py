import unittest

from application.visualization.grouping import group_rotation_blocks_by_frequency


class VisualizationGroupingTest(unittest.TestCase):
    def test_groups_rotations_by_generator_frequency_and_power(self):
        data = [
            {
                "freq_1": 2.0,
                "freq_2": 20.0,
                "amp_1": -1.0,
                "amp_2": -2.0,
                "rotation_angle": 10.0,
            },
            {
                "freq_1": 1.0,
                "freq_2": 10.0,
                "amp_1": -1.0,
                "amp_2": -2.0,
                "rotation_angle": 20.0,
            },
            {
                "freq_1": 1.0,
                "freq_2": 10.0,
                "amp_1": -1.0,
                "amp_2": -2.0,
                "rotation_angle": 0.0,
            },
            {
                "freq_1": 2.0,
                "freq_2": 20.0,
                "amp_1": -1.0,
                "amp_2": -2.0,
                "rotation_angle": 0.0,
            },
        ]

        groups = group_rotation_blocks_by_frequency(data)

        self.assertEqual(len(groups), 2)
        self.assertEqual([item["rotation_angle"] for item in groups[0]], [0.0, 10.0])
        self.assertEqual([item["rotation_angle"] for item in groups[1]], [0.0, 20.0])

    def test_groups_without_generators_by_vna_cw_frequency(self):
        data = [
            {
                "freq_1": None,
                "freq_2": None,
                "amp_1": None,
                "amp_2": None,
                "vna_cw_frequency_hz": 2.0e9,
                "rotation_angle": 10.0,
            },
            {
                "freq_1": None,
                "freq_2": None,
                "amp_1": None,
                "amp_2": None,
                "vna_cw_frequency_hz": 1.0e9,
                "rotation_angle": 20.0,
            },
            {
                "freq_1": None,
                "freq_2": None,
                "amp_1": None,
                "amp_2": None,
                "vna_cw_frequency_hz": 1.0e9,
                "rotation_angle": 0.0,
            },
        ]

        groups = group_rotation_blocks_by_frequency(data)

        self.assertEqual(len(groups), 2)
        self.assertEqual([item["rotation_angle"] for item in groups[0]], [10.0])
        self.assertEqual([item["rotation_angle"] for item in groups[1]], [0.0, 20.0])


if __name__ == "__main__":
    unittest.main()
