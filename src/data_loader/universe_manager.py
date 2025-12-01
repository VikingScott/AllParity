import pandas as pd
import yfinance as yf
from pathlib import Path
import sys
import time

# ==========================================
# 配置与路径设置
# ==========================================
# 确保能导入 config 模块
current_file = Path(__file__).resolve()
PROJECT_ROOT = current_file.parent.parent.parent
sys.path.append(str(PROJECT_ROOT))

CONFIG_FILE = PROJECT_ROOT / "config" / "etf_universe.csv"

# 尝试导入预设组合
try:
    from config import etf_bundles
    BUNDLES_AVAILABLE = True
except ImportError:
    BUNDLES_AVAILABLE = False
    print("⚠️  Warning: Could not import config.etf_bundles. Ensure the file exists.")

# 预定义的类别选项
ASSET_CLASSES = ['Equity', 'Fixed Income', 'Alternative', 'Multi-Asset', 'Cash', 'Index']

class UniverseManager:
    def __init__(self):
        self.df = self.load_universe()

    def load_universe(self):
        if not CONFIG_FILE.exists():
            print(f"Creating new universe file at {CONFIG_FILE}")
            return pd.DataFrame(columns=['ticker', 'yf_ticker', 'name', 'asset_class', 'category', 'source'])
        return pd.read_csv(CONFIG_FILE, dtype=str)

    def save_universe(self):
        self.df.to_csv(CONFIG_FILE, index=False)
        print(f"💾 Database saved to {CONFIG_FILE}")

    def check_exists(self, input_str):
        """双重检查：既查 ticker 也查 yf_ticker"""
        match_ticker = self.df[self.df['ticker'] == input_str]
        if not match_ticker.empty: return match_ticker.iloc[0]
        
        match_yf = self.df[self.df['yf_ticker'] == input_str]
        if not match_yf.empty: return match_yf.iloc[0]
            
        return None

    def guess_classification(self, info):
        """智能分类逻辑"""
        name = info.get('shortName', '') + " " + info.get('longName', '')
        category = info.get('category', '') 
        summary = info.get('longBusinessSummary', '')
        text = (name + " " + category + " " + summary).lower()
        
        # 1. Asset Class
        asset_class = "Equity" 
        if any(x in text for x in ['treasury', 'bond', 'fixed income', 'debt', 'aggregate', 'yield']):
            asset_class = "Fixed Income"
        elif any(x in text for x in ['bitcoin', 'crypto', 'coin', 'gold', 'silver', 'commodity', 'reit', 'real estate', 'future']):
            asset_class = "Alternative"
        elif 'allocation' in text or '60/40' in text:
            asset_class = "Multi-Asset"

        # 2. Category
        cat_guess = "General"
        if "treasury" in text:
            if "0-3" in text or "short" in text: cat_guess = "US Treasury (Short)"
            elif "20+" in text or "long" in text: cat_guess = "US Treasury (Long)"
            else: cat_guess = "US Treasury"
        elif "emerging" in text: cat_guess = "Emerging Markets"
        elif "japan" in text: cat_guess = "Country (Japan)"
        elif "germany" in text: cat_guess = "Country (Germany)"
        elif "uk" in text or "united kingdom" in text: cat_guess = "Country (UK)"
        elif "gold" in text: cat_guess = "Precious Metals"
        elif "bitcoin" in text: cat_guess = "Crypto"
        elif "real estate" in text or "reit" in text: cat_guess = "Real Estate"
        elif "tech" in text: cat_guess = "Sector (Tech)"
        elif category: cat_guess = category
            
        return asset_class, cat_guess

    def fetch_and_add(self, ticker_input, interactive=True):
        """核心添加逻辑：支持交互模式和静默模式"""
        ticker_input = ticker_input.strip().upper()
        
        # 查重
        existing = self.check_exists(ticker_input)
        if existing is not None:
            if interactive:
                print(f"⚠️  {ticker_input} already exists as {existing['ticker']} ({existing['name']})")
            return False

        if interactive: print(f"🔍 Fetching metadata for {ticker_input}...")
        
        try:
            t = yf.Ticker(ticker_input)
            info = t.info
            
            # Crypto 容错
            if not info or 'regularMarketPrice' not in info:
                if '-' not in ticker_input:
                    t_crypto = yf.Ticker(f"{ticker_input}-USD")
                    if t_crypto.info and 'regularMarketPrice' in t_crypto.info:
                        t = t_crypto
                        info = t.info
                        ticker_input = f"{ticker_input}-USD"
            
            name = info.get('shortName', info.get('longName', 'Unknown Name'))
            rec_class, rec_cat = self.guess_classification(info)
            
            if interactive:
                print(f"   Found: {name}")
                print(f"   Class: {rec_class} | Cat: {rec_cat}")
                confirm = input("   Add this? [y/n/edit]: ").lower()
            else:
                # 静默模式默认同意，除非名字是 Unknown
                if name == "Unknown Name":
                    print(f"❌ Failed to fetch data for {ticker_input}. Skipping.")
                    return False
                confirm = 'y'
                print(f"   [Auto-Add] {ticker_input}: {name} ({rec_cat})")

            final_class, final_cat, final_name, final_yf = rec_class, rec_cat, name, ticker_input

            if confirm == 'edit':
                final_name = input(f"Name [{name}]: ").strip() or name
                final_class = input(f"Class [{rec_class}]: ").strip() or rec_class
                final_cat = input(f"Category [{rec_cat}]: ").strip() or rec_cat
                final_yf = input(f"YF Symbol [{ticker_input}]: ").strip() or ticker_input
            elif confirm != 'y':
                return False

            # 清洗
            clean_ticker = final_yf.replace("-", "").replace("^", "")
            if final_class == 'Alternative' and '-USD' in final_yf: 
                 clean_ticker = final_yf.replace("-USD", "")

            new_row = {
                'ticker': clean_ticker,
                'yf_ticker': final_yf,
                'name': final_name,
                'asset_class': final_class,
                'category': final_cat,
                'source': 'yahoo'
            }
            
            self.df = pd.concat([self.df, pd.DataFrame([new_row])], ignore_index=True)
            return True

        except Exception as e:
            print(f"❌ Error processing {ticker_input}: {e}")
            return False

    def menu_import_bundle(self):
        if not BUNDLES_AVAILABLE:
            print("❌ Bundle config not found.")
            return

        while True:
            print("\n" + "="*40)
            print("📦 IMPORT FROM BUNDLES")
            print("="*40)
            
            bundle_names = list(etf_bundles.ALL_BUNDLES.keys())
            for i, name in enumerate(bundle_names):
                # 计算该 bundle 里有多少已经存在了
                tickers = etf_bundles.ALL_BUNDLES[name]
                existing_count = sum(1 for t in tickers if self.check_exists(t) is not None)
                print(f"[{i+1}] {name:<15} ({existing_count}/{len(tickers)} exists)")
            
            print(f"[{len(bundle_names)+1}] Back to Main Menu")
            
            choice = input("\nSelect Bundle to Import: ")
            try:
                idx = int(choice) - 1
                if idx == len(bundle_names): break
                
                if 0 <= idx < len(bundle_names):
                    target_bundle_name = bundle_names[idx]
                    target_tickers = etf_bundles.ALL_BUNDLES[target_bundle_name]
                    
                    print(f"\n🚀 Processing {target_bundle_name}...")
                    added_count = 0
                    for t in target_tickers:
                        # 稍微停顿防封
                        if self.fetch_and_add(t, interactive=False):
                            added_count += 1
                            time.sleep(0.5) 
                        else:
                            # 即使没添加（已存在），也打印一个小点表示进度
                            print(f"   . {t} checked")
                    
                    if added_count > 0:
                        self.save_universe()
                        print(f"\n✅ Successfully added {added_count} new assets from {target_bundle_name}.")
                    else:
                        print("\n✨ All assets in this bundle are already in your universe.")
                    
                    input("\nPress Enter to continue...")

            except ValueError:
                pass

    def list_current_universe(self):
        print("\n" + "="*80)
        print(f"{'Ticker':<8} | {'Class':<12} | {'Category':<20} | {'Name'}")
        print("-" * 80)
        for _, row in self.df.iterrows():
            # [Fix] 增加 name 的显示宽度，防止 EWU 显示不全
            print(f"{row['ticker']:<8} | {row['asset_class']:<12} | {row['category'][:20]:<20} | {row['name'][:50]}")
        print("=" * 80)
        input("Press Enter...")

    def run(self):
        while True:
            print("\n" + "="*40)
            print("🤖 UNIVERSE MANAGER V2.0")
            print("="*40)
            print("[1] ➕ Add Single Ticker (Interactive)")
            print("[2] 📦 Import from ETF Bundles (Bulk)")
            print("[3] 📜 List Current Universe")
            print("[4] 💾 Force Save & Exit")
            print("[q] Quit")
            
            choice = input("Select: ").strip().lower()
            
            if choice == '1':
                t = input("Ticker: ")
                if self.fetch_and_add(t, interactive=True):
                    self.save_universe()
            elif choice == '2':
                self.menu_import_bundle()
            elif choice == '3':
                self.list_current_universe()
            elif choice == '4':
                self.save_universe()
                break
            elif choice == 'q':
                break

if __name__ == "__main__":
    mgr = UniverseManager()
    mgr.run()