import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cpi.model import import_workbook, ROOT

p=argparse.ArgumentParser()
p.add_argument('workbook',type=Path)
args=p.parse_args()
print(f'Imported {import_workbook(args.workbook)} observations; original file unchanged.')
