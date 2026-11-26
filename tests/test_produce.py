import unittest
from produce import stamp, validate_cues, split_cues, clean_spec
class TimingTests(unittest.TestCase):
    def test_stamp(self):
        self.assertEqual(stamp(61.234),"00:01:01,234")
    def test_bounds(self):
        self.assertEqual(validate_cues([(0,3,"a")],2),[(0,2,"a")])
    def test_overlap(self):
        with self.assertRaises(ValueError):
            validate_cues([(0,2,"a"),(1,3,"b")],4)
    def test_split(self):
        cues=split_cues([(0,5,"one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen")],720,1280,"en")
        self.assertAlmostEqual(cues[-1][1],5)
    def test_missing_voice(self):
        with self.assertRaises(ValueError):
            clean_spec({"title":"x","language":"en","width":1280,"height":720,"scenes":[{"heading":"x","narration":"x"}]})
if __name__=="__main__":unittest.main()
