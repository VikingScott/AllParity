import pandas as pd
from pathlib import Path

# 配置路径
PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUT_FILE = PROJECT_ROOT / "config" / "etf_universe.csv"
OUTPUT_FILE = PROJECT_ROOT / "config" / "etf_universe_tagged.csv"

def clean_universe():
    print(f"🧹 Cleaning Universe: {INPUT_FILE}")
    df = pd.read_csv(INPUT_FILE)
    
    # 1. 初始化新列
    df['tier'] = 'Satellite' # 默认为卫星资产
    df['action'] = 'Keep'    # 默认为保留
    df['note'] = ''

    # 2. 规则引擎 (Rule-based Cleaning)
    
    # --- 规则 A: 剔除 Fund of Funds / 混合资产 ---
    # 理由: 无法进行纯粹的因子归因
    fof_keywords = ['Allocation', 'Portfolio', 'Balanced', 'Target']
    mask_fof = df['name'].str.contains('|'.join(fof_keywords), case=False, na=False) | \
               (df['asset_class'] == 'Multi-Asset')
    
    df.loc[mask_fof, 'action'] = 'Drop'
    df.loc[mask_fof, 'note'] = 'Fund of Funds (Mix)'

    # --- 规则 B: 标记核心资产 (Core) ---
    # 这些是构建宏观对冲的基础
    core_tickers = [
        'SPY', 'QQQ', 'IWM',       # 美股核心
        'EFA', 'EEM',              # 全球核心
        'TLT', 'IEF', 'SHY',       # 美债核心
        'GLD', 'DBC', 'VNQ',       # 另类核心
        'LQD', 'HYG'               # 信用债核心
    ]
    df.loc[df['ticker'].isin(core_tickers), 'tier'] = 'Core'

    # --- 规则 C: 标记冗余 (Redundancy) ---
    # 理由: 已经有了 SPY，不需要 VOO/IVV；已经有了 AGG，不需要 BND
    redundant_map = {
        'VOO': 'Drop (Use SPY)',
        'IVV': 'Drop (Use SPY)',
        'ITOT': 'Drop (Use SPY/IWM)',
        'BND': 'Drop (Use AGG)',
        'IAU': 'Drop (Use GLD)',
        'IAGG': 'Drop (Use AGG for now)',
        'GOVT': 'Drop (Use IEF/TLT combo)',
        'SCHG': 'Drop (Use QQQ)',
        'SPYM': 'Drop (Market Neutral is Strategy, not Asset)'
    }
    
    for t, reason in redundant_map.items():
        mask = df['ticker'] == t
        df.loc[mask, 'action'] = 'Drop'
        df.loc[mask, 'note'] = reason

    # --- 规则 D: 标记波动率指数 ---
    # 理由: 它们不是可投资资产，而是参考指标
    mask_idx = df['asset_class'] == 'Index'
    df.loc[mask_idx, 'action'] = 'Reference' # 只看不买
    df.loc[mask_idx, 'note'] = 'Macro Indicator'

    # --- 规则 E: 标记行业与因子 ---
    mask_sector = df['category'].str.contains('Sector', na=False)
    df.loc[mask_sector, 'tier'] = 'Sector'
    
    mask_factor = df['category'].str.contains('Factor', na=False)
    df.loc[mask_factor, 'tier'] = 'Factor'

    # 3. 输出统计
    print("\n📊 Cleaning Summary:")
    print(df['action'].value_counts())
    
    # 4. 保存
    df.to_csv(OUTPUT_FILE, index=False)
    print(f"\n✅ Tagged universe saved to: {OUTPUT_FILE}")
    print("👉 Please open this CSV manually and verify the 'action' column.")

if __name__ == "__main__":
    clean_universe()