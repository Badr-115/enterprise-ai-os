from __future__ import annotations
import io
import hashlib
import os
from pathlib import Path
import uuid
from dataclasses import dataclass
import numpy as np
import pandas as pd

MAX_BYTES=5*1024*1024
MAX_ROWS=10000
REQUIRED_COLUMNS={"date","revenue","cost","units"}
ARABIC_DIGITS=str.maketrans("٠١٢٣٤٥٦٧٨٩٬٫","0123456789,.")
COLUMN_ALIASES={
 "التاريخ":"date","تاريخ":"date",
 "الإيرادات":"revenue","الإيراد":"revenue","المبيعات":"revenue",
 "التكلفة":"cost","التكاليف":"cost","المصروفات":"cost",
 "الوحدات":"units","وحدة":"units","الكمية":"units",
}

@dataclass
class DatasetResult:
 id:str; name:str; rows:int; columns:list[str]; summary:dict; warnings:list[str]; kpis:dict; anomalies:list[dict]; preview:list[dict]; quality:dict; created_at:str; content_hash:str; records:list[dict]


def _quality_issue(issue_type: str, severity: str, message: str, columns: list[str], rows: list[int], count: int, details: list[str] | None = None) -> dict:
 return {'type':issue_type,'severity':severity,'message':message,'columns':columns,'rows':rows[:50],'count':count,'details':details or []}

def normalize_column(column: object) -> str:
 normalized=" ".join(str(column).replace("\ufeff","").strip().lower().split())
 return COLUMN_ALIASES.get(normalized, normalized)

def _read_source(content: bytes | Path, name: str) -> pd.DataFrame:
 if isinstance(content, Path):
  if content.stat().st_size == 0:
   raise ValueError("The uploaded file is empty")
  if content.stat().st_size > MAX_BYTES:
   raise ValueError("File exceeds the 5 MB upload limit")
  source: object = content
 else:
  if not content:
   raise ValueError("The uploaded file is empty")
  if len(content)>MAX_BYTES:
   raise ValueError("File exceeds the 5 MB upload limit")
  source = io.BytesIO(content)
 try:
  if name.lower().endswith('.xlsx'):
   return pd.read_excel(source, engine='openpyxl')
  if name.lower().endswith('.csv'):
   return pd.read_csv(source)
  raise ValueError("Only CSV and XLSX files are supported")
 except Exception as e:
  if isinstance(e, ValueError) and str(e) == "Only CSV and XLSX files are supported":
   raise
  raise ValueError("The file could not be parsed safely. Check that it is a valid UTF-8 CSV or XLSX file.") from e

def analyze_csv(content: bytes, name: str) -> DatasetResult:
 df = _read_source(content, name)
 return _analyze_frame(df, content, name)


def analyze_file(path: str | os.PathLike[str], name: str, content_hash: str) -> DatasetResult:
 """Analyze a bounded temporary upload without making another whole-file copy."""
 source = Path(path)
 df = _read_source(source, name)
 return _analyze_frame(df, source, name, content_hash)


def _analyze_frame(
 content_frame: pd.DataFrame,
 source: bytes | Path,
 name: str,
 content_hash: str | None = None,
) -> DatasetResult:
 df = content_frame
 if len(df)>MAX_ROWS:
  raise ValueError("File exceeds the 10,000 row limit")
 if len(df)==0:
  raise ValueError("The CSV has a header but no data rows")
 raw_df=df.copy()
 normalized_columns=[normalize_column(c) for c in raw_df.columns]
 raw_df.columns=normalized_columns
 raw_columns=[str(column) for column in raw_df.columns]
 df.columns=normalized_columns
 duplicate_columns=sorted({column for column in normalized_columns if normalized_columns.count(column)>1})
 if duplicate_columns:
  raise ValueError(f"Duplicate column names are not supported: {', '.join(duplicate_columns)}")
 missing=REQUIRED_COLUMNS-set(df.columns)
 if missing:
  raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")
 for c in ['revenue','cost','units']:
  df[c]=pd.to_numeric(df[c].astype(str).str.translate(ARABIC_DIGITS), errors='coerce')
 df['date']=pd.to_datetime(df['date'], errors='coerce')
 quality_issues=[]
 for c in REQUIRED_COLUMNS:
  missing_mask=raw_df[c].isna() | raw_df[c].astype(str).str.strip().eq('')
  missing_rows=[int(index)+2 for index in raw_df.index[missing_mask]]
  if missing_rows:
   quality_issues.append(_quality_issue('missing_values','warning',f'Missing values detected in {c}',[c],missing_rows,len(missing_rows)))
 duplicate_mask=raw_df.duplicated(keep=False)
 duplicate_rows=[int(index)+2 for index in raw_df.index[duplicate_mask]]
 if duplicate_rows:
  quality_issues.append(_quality_issue('duplicate_records','warning','Duplicate records detected',raw_columns,duplicate_rows,len(duplicate_rows)//2))
 invalid_date_mask=df['date'].isna() & raw_df['date'].notna()
 invalid_date_rows=[int(index)+2 for index in df.index[invalid_date_mask]]
 if invalid_date_rows:
  quality_issues.append(_quality_issue('invalid_dates','error','Invalid date values detected',['date'],invalid_date_rows,len(invalid_date_rows)))
 for c in ['revenue','cost','units']:
  original=raw_df[c].astype(str).str.strip()
  invalid_mask=df[c].isna() & raw_df[c].notna() & (original != '')
  invalid_rows=[int(index)+2 for index in df.index[invalid_mask]]
  if invalid_rows:
   quality_issues.append(_quality_issue('invalid_numeric','error',f'Invalid numeric values detected in {c}',[c],invalid_rows,len(invalid_rows)))
 for c in raw_df.columns:
  if c in REQUIRED_COLUMNS or not (pd.api.types.is_object_dtype(raw_df[c]) or pd.api.types.is_string_dtype(raw_df[c])):
   continue
  values=raw_df[c].dropna().astype(str)
  normalized=values.str.strip().str.casefold()
  variants={}
  for original, key in zip(values, normalized):
   variants.setdefault(key,set()).add(original)
  inconsistent=[sorted(items) for items in variants.values() if len(items)>1]
  if inconsistent:
   details=[', '.join(items) for items in inconsistent[:10]]
   quality_issues.append(_quality_issue('inconsistent_categories','warning',f'Inconsistent category variants detected in {c}',[c],[],sum(len(items)-1 for items in inconsistent),details))
 extra_columns=[column for column in normalized_columns if column not in REQUIRED_COLUMNS]
 if extra_columns:
  quality_issues.append(_quality_issue('schema_problem','info','Additional columns are available for analysis',extra_columns,[],len(extra_columns),extra_columns))
 warnings=[]
 for c in REQUIRED_COLUMNS:
  n=int(df[c].isna().sum())
  if n:
   warnings.append(f"{n} missing or malformed value(s) in {c}")
 valid=df.dropna(subset=['revenue','cost','units'])
 if valid.empty:
  raise ValueError("The CSV contains no rows with valid revenue, cost, and units values")
 revenue=float(valid.revenue.sum()); cost=float(valid.cost.sum()); units=float(valid.units.sum())
 margin=revenue-cost
 daily=valid.assign(day=df.loc[valid.index,'date'].dt.strftime('%Y-%m-%d')).groupby('day',dropna=True).revenue.sum().reset_index().tail(30)
 anomalies=[]
 if len(valid)>=4:
  q1,q3=valid.revenue.quantile([.25,.75]); iqr=q3-q1; lo,hi=q1-1.5*iqr,q3+1.5*iqr
  for idx,row in valid[(valid.revenue<lo)|(valid.revenue>hi)].head(50).iterrows():
   anomalies.append({'row':int(idx)+2,'metric':'revenue','value':float(row.revenue),'reason':'Outside 1.5×IQR bounds','bounds':[float(lo),float(hi)]})
 for anomaly in anomalies:
  quality_issues.append(_quality_issue('outlier','warning','Suspicious revenue outlier detected',['revenue'],[anomaly['row']],1,[anomaly['reason']]))
 date_values=df.date.dropna()
 date_range=[date_values.min().date().isoformat(),date_values.max().date().isoformat()] if not date_values.empty else [None,None]
 return DatasetResult(
  str(uuid.uuid4()),name,len(df),list(df.columns),
  {'numeric_columns':list(df.select_dtypes(include=np.number).columns),'date_range':date_range},
  warnings,
  {'total_revenue':round(revenue,2),'total_cost':round(cost,2),'total_units':round(units,2),
   'gross_margin':round(margin,2),'margin_rate':round(margin/revenue*100,2) if revenue else None,
   'daily_revenue':[{'date':r.day,'value':round(float(r.revenue),2)} for r in daily.itertuples()]},
  anomalies,df.head(10).where(pd.notna(df),None).to_dict('records'),
  {'issues':quality_issues,'issue_count':len(quality_issues),'rows_affected':len({row for issue in quality_issues for row in issue['rows']}),
   'has_blocking_issues':any(issue['severity']=='error' for issue in quality_issues)},
  pd.Timestamp.now(tz='UTC').isoformat(),
  content_hash or hashlib.sha256(source if isinstance(source, bytes) else source.read_bytes()).hexdigest(),
  df.where(pd.notna(df),None).to_dict('records'))
