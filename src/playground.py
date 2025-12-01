import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta

# ==========================================
# 配置与数据加载
# ==========================================
PROJECT_ROOT = Path(__file__).parent
if (PROJECT_ROOT / "data").exists():
    BASE_DIR = PROJECT_ROOT
else:
    BASE_DIR = PROJECT_ROOT.parent

RETURNS_PATH = BASE_DIR / "data" / "processed" / "asset_returns.csv"
CONFIG_PATH = BASE_DIR / "config" / "etf_universe.csv"
OUTPUT_FILE = PROJECT_ROOT / "performance_tbl.txt"
RF_RATE = 0.04 

class PortfolioPlayground:
    def __init__(self):
        self.returns_df = self.load_returns()
        self.meta_df = self.load_metadata()
        self.selected_tickers = []
        self.period_returns = pd.DataFrame()

    def load_returns(self):
        if not RETURNS_PATH.exists():
            print(f"❌ Error: Could not find {RETURNS_PATH}")
            return pd.DataFrame()
        return pd.read_csv(RETURNS_PATH, index_col=0, parse_dates=True)

    def load_metadata(self):
        if not CONFIG_PATH.exists():
            return pd.DataFrame()
        try:
            df = pd.read_csv(CONFIG_PATH)
            valid_tickers = self.returns_df.columns.tolist()
            return df[df['ticker'].isin(valid_tickers)]
        except:
            return pd.DataFrame()

    def clear_screen(self):
        print("\n" * 2)
        print("="*60)

    # ==========================
    # Step 1: 资产选择
    # ==========================
    def select_assets(self):
        # 如果已有选择，保留，允许增删
        while True:
            self.clear_screen()
            print("🛒 ASSET SELECTION MENU")
            print(f"Current Portfolio: {self.selected_tickers}")
            print("-" * 60)
            
            classes = self.meta_df['asset_class'].unique()
            for idx, cls in enumerate(classes):
                print(f"[{idx+1}] {cls}")
            print(f"[{len(classes)+1}] ✅ Confirm & Next Step")
            print(f"[{len(classes)+2}] ❌ Clear All")
            
            choice = input("\nSelect ID: ")
            
            try:
                choice_idx = int(choice) - 1
                if choice_idx == len(classes): # Confirm
                    if not self.selected_tickers:
                        print("⚠️  Select at least one asset!")
                        input("Press Enter...")
                        continue
                    return "NEXT"
                
                if choice_idx == len(classes) + 1: # Clear
                    self.selected_tickers = []
                    continue

                if 0 <= choice_idx < len(classes):
                    self.browse_category(classes[choice_idx])
            except ValueError:
                pass

    def browse_category(self, asset_class):
        subset = self.meta_df[self.meta_df['asset_class'] == asset_class]
        while True:
            self.clear_screen()
            print(f"📂 Browsing: {asset_class}")
            print("-" * 60)
            print(f"{'ID':<4} | {'Ticker':<6} | {'Start Date':<12} | {'Name'}")
            print("-" * 60)
            
            options = subset.reset_index(drop=True)
            for idx, row in options.iterrows():
                mark = "✅" if row['ticker'] in self.selected_tickers else "  "
                # 获取该资产的开始时间
                start_dt = "N/A"
                if row['ticker'] in self.returns_df.columns:
                    first_idx = self.returns_df[row['ticker']].first_valid_index()
                    if first_idx: start_dt = first_idx.strftime('%Y-%m-%d')

                print(f"[{idx+1}]  {mark} {row['ticker']:<6} | {start_dt:<12} | {row['name'][:30]}")
            
            print("\nEnter ID to toggle, or 'b' to Go Back.")
            inp = input("Choice: ").strip()
            if inp.lower() == 'b': break
            
            try:
                idx = int(inp) - 1
                if 0 <= idx < len(options):
                    t = options.iloc[idx]['ticker']
                    if t in self.selected_tickers: self.selected_tickers.remove(t)
                    else: self.selected_tickers.append(t)
            except: pass

    # ==========================
    # Step 2: 时间选择 (增强版)
    # ==========================
    def select_timeframe(self):
        self.clear_screen()
        print("⏳ TIME MACHINE & DATA CHECK")
        print("-" * 60)
        
        subset = self.returns_df[self.selected_tickers]
        
        # 1. 展示每个资产的时间范围
        print(f"{'Ticker':<8} | {'Start Date':<12} | {'History Length'}")
        print("-" * 60)
        
        starts = []
        for t in self.selected_tickers:
            first = subset[t].first_valid_index()
            if first is None:
                print(f"{t:<8} | {'NO DATA':<12} | 0 days")
                starts.append(pd.Timestamp.max)
            else:
                days = (subset.index[-1] - first).days
                print(f"{t:<8} | {first.date()}   | {days/365.25:.1f} years")
                starts.append(first)
        
        common_start = max(starts)
        full_end = subset.index[-1]
        
        print("-" * 60)
        print(f"🔗 EFFECTIVE COMMON RANGE: {common_start.date()} to {full_end.date()}")
        print("-" * 60)

        print("\n[1] Last 1 Year")
        print("[2] Last 3 Years")
        print("[3] Max Common History (From Effective Start)")
        print("[4] Custom Start Date")
        print("[b] Back to Asset Selection")
        
        choice = input("\nSelect Timeframe: ").strip()
        
        if choice.lower() == 'b':
            return "BACK"
        
        start_date = common_start
        end_date = full_end
        
        if choice == '1':
            start_date = end_date - timedelta(days=365)
        elif choice == '2':
            start_date = end_date - timedelta(days=365*3)
        elif choice == '4':
            d_str = input("Enter Start (YYYY-MM-DD): ")
            try:
                start_date = datetime.strptime(d_str, "%Y-%m-%d")
            except:
                print("Invalid date.")
                return "BACK"
        
        # 强制对齐到有效开始日期
        if start_date < common_start:
            print(f"⚠️  Adjusting start date to {common_start.date()} (Data limit)")
            start_date = common_start

        self.period_returns = subset.loc[start_date:end_date].dropna()
        
        if self.period_returns.empty:
            print("⚠️  No data in this range!")
            input("Press Enter...")
            return "BACK"
            
        print(f"✅ Range Selected: {self.period_returns.index[0].date()} to {self.period_returns.index[-1].date()}")
        return "NEXT"

    # ==========================
    # Step 3: 策略配置
    # ==========================
    def configure_strategy(self):
        while True:
            self.clear_screen()
            print("🧠 STRATEGY ENGINE")
            print(f"Assets: {', '.join(self.selected_tickers)}")
            print("-" * 60)
            print("[1] ⚖️  Equal Weight")
            print("[2] 🛡️  Risk Parity")
            print("[3] 🎛️  Manual Weights")
            print("[b] Back")
            
            choice = input("Select: ").strip()
            if choice.lower() == 'b': return "BACK"
            
            weights = {}
            if choice == '1':
                w = 1.0/len(self.selected_tickers)
                weights = {t: w for t in self.selected_tickers}
                return weights
            elif choice == '2':
                vols = self.period_returns.std()
                inv = 1.0/vols
                weights = (inv/inv.sum()).to_dict()
                return weights
            elif choice == '3':
                rem = 1.0
                for i,t in enumerate(self.selected_tickers):
                    if i==len(self.selected_tickers)-1:
                        weights[t] = rem
                    else:
                        try: w = float(input(f"{t} (Rem {rem:.2f}): "))
                        except: w = 0.0
                        weights[t] = w
                        rem -= w
                return weights

    # ==========================
    # Step 4: 回测与详细报告
    # ==========================
    def run_backtest(self, weights):
        self.clear_screen()
        print("🚀 SIMULATING...")
        
        w_series = pd.Series(weights)
        daily_ret = self.period_returns.dot(w_series)
        
        # 资金曲线
        INITIAL_CAPITAL = 100000
        equity_curve = INITIAL_CAPITAL * (1 + daily_ret).cumprod()
        
        # --- 月度统计 ---
        # 重新采样为月度
        monthly_groups = daily_ret.groupby([daily_ret.index.year, daily_ret.index.month])
        
        report_lines = []
        report_lines.append(f"BACKTEST REPORT - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        report_lines.append("="*80)
        report_lines.append(f"Range: {self.period_returns.index[0].date()} to {self.period_returns.index[-1].date()}")
        report_lines.append(f"Initial Investment: ${INITIAL_CAPITAL:,.2f}")
        report_lines.append("Portfolio:")
        for t,w in weights.items(): report_lines.append(f"  {t:<6}: {w*100:.1f}%")
        report_lines.append("-" * 80)
        report_lines.append(f"{'MONTH':<10} | {'RETURN':<8} | {'BALANCE ($)':<15} | {'DRAWDOWN':<8}")
        report_lines.append("-" * 80)
        
        current_balance = INITIAL_CAPITAL
        peak_balance = INITIAL_CAPITAL
        
        for (year, month), data in monthly_groups:
            # 当月收益
            m_ret = (1 + data).prod() - 1
            # 当月结束时的资金
            month_end_date = data.index[-1]
            current_balance = equity_curve.loc[month_end_date]
            
            # 动态最大回撤 (截止到当月末)
            peak_balance = max(peak_balance, current_balance)
            dd = (current_balance - peak_balance) / peak_balance
            
            line = f"{year}-{month:02d}    | {m_ret*100:6.2f}% | ${current_balance:13,.2f} | {dd*100:6.1f}%"
            report_lines.append(line)
            
        # 总计指标
        total_ret = (equity_curve.iloc[-1] / INITIAL_CAPITAL) - 1
        days = len(daily_ret)
        years = days/252.0
        cagr = (1+total_ret)**(1/years)-1 if years>0 else 0
        vol = daily_ret.std()*np.sqrt(252)
        sharpe = (cagr - RF_RATE)/vol if vol>0 else 0
        
        # 全局最大回撤
        roll_max = equity_curve.cummax()
        dd_series = (equity_curve - roll_max) / roll_max
        max_dd = dd_series.min()

        report_lines.append("=" * 80)
        report_lines.append(f"FINAL BALANCE:   ${current_balance:,.2f}")
        report_lines.append(f"CAGR:            {cagr*100:.2f}%")
        report_lines.append(f"VOLATILITY:      {vol*100:.2f}%")
        report_lines.append(f"SHARPE:          {sharpe:.2f}")
        report_lines.append(f"MAX DRAWDOWN:    {max_dd*100:.2f}%")
        report_lines.append("=" * 80 + "\n")
        
        # 打印到屏幕 (只打最后几行总结，避免刷屏)
        print("\n".join(report_lines[-8:]))
        print(f"\n📄 Detailed monthly log saved to {OUTPUT_FILE}")

        # 保存
        with open(OUTPUT_FILE, "a") as f:
            f.write("\n".join(report_lines))

        input("\nPress Enter to Start Over...")

    def run(self):
        while True:
            # State Machine Loop
            res = self.select_assets()
            if res != "NEXT": continue # Loop back
            
            res = self.select_timeframe()
            if res == "BACK": continue 
            
            weights = self.configure_strategy()
            if weights == "BACK": continue
            
            self.run_backtest(weights)

if __name__ == "__main__":
    app = PortfolioPlayground()
    app.run()