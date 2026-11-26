import io,unittest
from datetime import datetime
import openpyxl
from cpi.pce_history import parse,HEADERS
class PceHistoryTest(unittest.TestCase):
    def workbook(self):
        w=openpyxl.Workbook();s=w.active;s.title='Datasheet';s.append(HEADERS)
        for n in range(101):s.append([datetime(2000+n//12,n%12+1,1),3,2,0,1,2,3,4])
        s.cell(2,2,'`');b=io.BytesIO();w.save(b);return b.getvalue()
    def test_real_schema_missing_values(self):
        rows=parse(self.workbook());self.assertEqual(len(rows),101);self.assertIsNone(rows[0]['headline']);self.assertEqual(rows[0]['p90'],4)
    def test_bad_schema_fails_closed(self):
        with self.assertRaises(Exception):parse(b'bad download')
