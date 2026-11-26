import io,unittest,zipfile,re
from datetime import datetime
import openpyxl
from cpi.pce_growth import parse,HEADERS
class PceGrowthTest(unittest.TestCase):
    def fixture(self,duplicate=False,outside=False):
        w=openpyxl.Workbook();s=w.active;s.title='Datasheet';s.append(['Unrelated',HEADERS['weight_pct'],'Month',HEADERS['items_pct']])
        for n in range(101):s.append([999,80.123456789,datetime(2000+n//12,n%12+1,1),60.987654321])
        s.cell(2,2,'#N/A')
        if duplicate:s.cell(3,3,s.cell(2,3).value)
        if outside:s.cell(4,2,101)
        b=io.BytesIO();w.save(b);return b.getvalue()
    def test_named_columns_units_missing_and_no_resmoothing(self):
        rows,columns=parse(self.fixture());self.assertEqual(len(rows),101);self.assertIsNone(rows[0]['weight_pct']);self.assertEqual(rows[0]['items_pct'],60.987654321);self.assertEqual(rows[1]['weight_pct'],80.123456789);self.assertEqual(columns['items_pct']['excel_column_1based'],4)
    def test_duplicate_month_rejected(self):
        with self.assertRaises(ValueError):parse(self.fixture(duplicate=True))
    def test_outside_percentage_rejected(self):
        with self.assertRaises(ValueError):parse(self.fixture(outside=True))
    def test_official_floating_sum_preserved(self):
        # openpyxl's writer rounds to 15 significant digits; preserve the source
        # Excel XML precision explicitly to reproduce the official workbook.
        source=zipfile.ZipFile(io.BytesIO(self.fixture()));b=io.BytesIO()
        with zipfile.ZipFile(b,'w') as out:
            for name in source.namelist():
                data=source.read(name)
                if name=='xl/worksheets/sheet1.xml':
                    data=re.sub(rb'(<c r="B4"[^>]*><v>)[^<]+',rb'\g<1>100.00000000000004',data)
                out.writestr(name,data)
        rows,_=parse(b.getvalue());self.assertEqual(rows[2]['weight_pct'],100.00000000000004)
