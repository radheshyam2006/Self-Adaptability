import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import pandas as pd, numpy as np, pickle, os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
EXCEL_FILE = os.path.join(PROJECT_DIR, 'data', 'TSMC28nm_DRV_ML_MAR6_LookUP_Table_Mar20_ML Predictions.xlsx')
CORNER_SHEETS = {'FF':'FF_vdd_temp','SS':'SS_vdd_test','TT':'TT_vdd_test','FS':'FS_vdd_test','SF':'SF_vdd_test'}
COL_NAMES = ['Corner','vreg','temperature','PULL_UP_RES','PULL_DN_RES','pmon_cmos_res','pmon_cmos','pvtp_raw','pvtn_raw','PULL_UP_RES_new','PULL_DN_RES_new']

def pad8(v):
    if pd.isna(v) or str(v).strip().lower()=='na': return None
    return str(v).replace('-','').strip().zfill(8)
def to_int(v):
    if v is None or pd.isna(v): return None
    try: return int(v,2)
    except: return None

all_d=[]
for c,s in CORNER_SHEETS.items():
    df=pd.read_excel(EXCEL_FILE, sheet_name=s, header=0).iloc[:,:11]
    df.columns=COL_NAMES
    for col in ['vreg','temperature','pmon_cmos_res','PULL_UP_RES','PULL_DN_RES','PULL_UP_RES_new','PULL_DN_RES_new']:
        df[col]=pd.to_numeric(df[col], errors='coerce')
    df['corner_label']=c
    df['pvtp_int']=df['pvtp_raw'].apply(pad8).apply(to_int)
    df['pvtn_int']=df['pvtn_raw'].apply(pad8).apply(to_int)
    all_d.append(df)
df=pd.concat(all_d, ignore_index=True).dropna(subset=['pvtp_int','pvtn_int','pmon_cmos_res','PULL_UP_RES_new','PULL_DN_RES_new'])

pmon_col = 'pmon_cmos_res'
pvtp_col = 'pvtp_int'
pvtn_col = 'pvtn_int'

print('=== CORRELATION MATRIX ===')
corr_cols = [pmon_col,'vreg','temperature',pvtp_col,pvtn_col]
cm = df[corr_cols].corr()
for c1 in [pmon_col,'vreg','temperature']:
    for c2 in [pvtp_col,pvtn_col]:
        val = cm.loc[c1,c2]
        print('  corr(%s, %s) = %.4f' % (c1, c2, val))

print()
print('=== PMON_CMOS_RES STATS ===')
pmin = df[pmon_col].min()
pmax = df[pmon_col].max()
pmax_int = int(round(pmax))
print('  min = %.0f' % pmin)
print('  max = %.0f' % pmax)
print('  round(max) = %d' % pmax_int)
print('  bit_length of max = %d' % pmax_int.bit_length())
print('  2^29 = %d' % (2**29))
print('  fits in 29 bits? %s' % (pmax_int < 2**29))

print()
print('=== FEATURE IMPORTANCE ===')
for name in ['best_model_pvtp_d14.pkl','best_model_pvtn_d14.pkl']:
    for d in ['.','ml']:
        p=os.path.join(d,name)
        if os.path.exists(p):
            with open(p,'rb') as f: m=pickle.load(f)
            fi = m.feature_importances_
            features = [pmon_col,'vreg','temperature']
            print('  %s:' % name)
            for fn,fv in zip(features,fi):
                print('    %s: %.4f (%.1f%%)' % (fn, fv, fv*100))
            break

print()
print('=== RESISTANCE PER CORNER ===')
for c in ['FF','SS','TT','FS','SF']:
    cdf = df[df['corner_label']==c]
    pu = cdf['PULL_UP_RES_new']
    pd2 = cdf['PULL_DN_RES_new']
    print('  %s: PU=%.2f-%.2f (mean=%.3f, err=%.3f ohm)' % (c, pu.min(), pu.max(), pu.mean(), abs(pu.mean()-50)))
    print('       PD=%.2f-%.2f (mean=%.3f, err=%.3f ohm)' % (c, pd2.min(), pd2.max(), pd2.mean(), abs(pd2.mean()-50)))

print()
print('=== QUANTIZATION STEP ===')
res_steps = []
for c in ['FF','SS','TT','FS','SF']:
    cdf = df[df['corner_label']==c]
    pvtp_unique = sorted(cdf[pvtp_col].unique())
    for i in range(1, len(pvtp_unique)):
        code1, code2 = pvtp_unique[i-1], pvtp_unique[i]
        r1 = cdf[cdf[pvtp_col]==code1]['PULL_UP_RES_new'].mean()
        r2 = cdf[cdf[pvtp_col]==code2]['PULL_UP_RES_new'].mean()
        if code2 != code1:
            step = abs(r2-r1)/abs(code2-code1)
            res_steps.append(step)
avg_step = np.mean(res_steps)
print('  Avg resistance change per 1 trim code step: %.3f ohms' % avg_step)
print('  So +/-1 trim code error => +/-%.3f ohms from target' % avg_step)

print()
print('=== TOTAL UNIQUE TRIM CODES ===')
print('  unique pvtp values globally: %d' % df[pvtp_col].nunique())
print('  unique pvtn values globally: %d' % df[pvtn_col].nunique())
for c in ['FF','SS','TT','FS','SF']:
    cdf = df[df['corner_label']==c]
    print('  %s: %d unique pvtp, %d unique pvtn' % (c, cdf[pvtp_col].nunique(), cdf[pvtn_col].nunique()))
