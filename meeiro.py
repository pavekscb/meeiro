import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
import requests
import json
import threading 
import time
import webbrowser
import os 
from urllib.parse import quote 

# --- КОНСТАНТЫ ПРИЛОЖЕНИЯ И ВЕРСИИ ---
CURRENT_VERSION = "1.0.0" # !!! Текущая версия программы (будет обновляться с каждым релизом)
URL_GITHUB_API = "https://api.github.com/repos/pavekscb/meeiro/releases/latest" 

# --- Файл и Константы для адреса кошелька ---
WALLET_FILE = "WALLET_ADDRESS.txt"
DEFAULT_EXAMPLE_ADDRESS = "0x9ba27fc8a65ba4507fc4cca1b456e119e4730b8d8cfaf72a2a486e6d0825b27b"
RAW_DATA_CORRECTION_FACTOR = 100 

# --- Константы Сети ---
DECIMALS = 8 
ACC_PRECISION = 100000000000 # 10^11
UPDATE_INTERVAL_SECONDS = 60 

MEE_COIN_T0_T1 = "0xe9c192ff55cffab3963c695cff6dbf9dad6aff2bb5ac19a6415cad26a81860d9::mee_coin::MeeCoin"

APTOS_LEDGER_URL = "https://fullnode.mainnet.aptoslabs.com/v1"
HARVEST_BASE_URL = "https://explorer.aptoslabs.com/account/0x514cfb77665f99a2e4c65a5614039c66d13e00e98daf4c86305651d29fd953e5/modules/run/Staking/harvest?network=mainnet"
ADD_MEE_URL = "https://explorer.aptoslabs.com/account/0x514cfb77665f99a2e4c65a5614039c66d13e00e98daf4c86305651d29fd953e5/modules/run/Staking/stake?network=mainnet"
UNSTAKE_BASE_URL = "https://explorer.aptoslabs.com/account/0x514cfb77665f99a2e4c65a5614039c66d13e00e98daf4c86305651d29fd953e5/modules/run/Staking/unstake?network=mainnet"

# КОНСТАНТЫ: Ссылки для кнопок
URL_SOURCE = "https://github.com/pavekscb/meeiro" 
URL_SITE = "https://meeiro.xyz/staking"
URL_GRAPH = "https://dexscreener.com/aptos/pcs-167"
URL_SWAP = "https://aptos.pancakeswap.finance/swap?outputCurrency=0x1%3A%3Aaptos_coin%3A%3AAptosCoin&inputCurrency=" + quote(MEE_COIN_T0_T1)
URL_SWAP_EARNIUM = "https://app.earnium.io/swap?from=" + quote(MEE_COIN_T0_T1) + "&to=0x1%3A%3Aaptos_coin%3A%3AAptosCoin"
URL_SUPPORT = "https://t.me/cripto_karta"

class UpdateChecker:
    """Класс для проверки обновлений на GitHub."""
    
    def __init__(self, current_version):
        self.current_version = self._normalize_version(current_version)

    def _normalize_version(self, version_str):
        """Преобразует строку версии (например, 'v1.0.0' или '1.0.0') в кортеж чисел."""
        version_str = version_str.lstrip('v').strip()
        try:
            return tuple(map(int, version_str.split('.')))
        except ValueError:
            # Возвращаем кортеж из нулей, если версия не парсится
            return (0, 0, 0) 
            
    def _is_newer(self, new_version_str):
        """Сравнивает новую версию с текущей."""
        new_version = self._normalize_version(new_version_str)
        return new_version > self.current_version

    def fetch_latest_release(self):
        """Получает информацию о последнем релизе с GitHub API."""
        try:
            response = requests.get(URL_GITHUB_API, timeout=5)
            response.raise_for_status()
            data = response.json()
            
            latest_version = data.get('tag_name', 'v0.0.0')
            download_url = data.get('html_url') # Ссылка на страницу релиза
            
            if self._is_newer(latest_version) and download_url:
                # Нормализуем версию для отображения (убираем 'v' если есть)
                display_version = latest_version.lstrip('v').strip()
                return display_version, download_url
            else:
                return None, None
                
        except requests.exceptions.RequestException:
            return False, None 

class MeeiroApp(tk.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self.master = master
        self.master.title(f"МОНИТОР СТЕЙКИНГА $MEE (APTOS) - v{CURRENT_VERSION}")
        
        # --- ЛОГИКА ЦЕНТРИРОВАНИЯ ОКНА ---
        window_width = 420
        window_height = 650
        
        # Получаем размеры экрана
        screen_width = self.master.winfo_screenwidth()
        screen_height = self.master.winfo_screenheight()
        
        # Вычисляем координаты для центрирования
        center_x = int((screen_width / 2) - (window_width / 2))
        center_y = int((screen_height / 2) - (window_height / 2))
        
        # Устанавливаем геометрию (размер + позиция)
        self.master.geometry(f'{window_width}x{window_height}+{center_x}+{center_y}')
        
        self.master.resizable(False, False)
        
        # --- Переменные состояния ---
        self.current_wallet_address = self._load_wallet_address() 
        self.mee_current_reward = 0.0 
        self.mee_rate_per_sec = 0.0
        self.countdown_val = UPDATE_INTERVAL_SECONDS
        self.simulation_job = None
        self.is_running = False
        self.update_checker = UpdateChecker(CURRENT_VERSION)
        
        # --- Анимация ---
        self.animation_frames = ['🌱', '🌿', '💰']
        self.current_frame_index = 0
        self.reward_ticker_var = tk.StringVar(value="[Загрузка]")

        # --- Ссылки на виджеты для безопасного обновления ---
        self.wallet_label_ref = None 
        self.update_status_label = None 
        
        self.create_widgets()
        self._start_app()
        
    def create_widgets(self):
        # Основной контейнер
        main_frame = tk.Frame(self.master, padx=10, pady=10)
        main_frame.pack(fill="both", expand=True)

        # Заголовок
        title_header = tk.Label(main_frame, text="МОНИТОР СТЕЙКИНГА $MEE (APTOS)", 
                                fg="#1E90FF", font=("Arial", 16, "bold"), 
                                pady=5, borderwidth=0, relief="flat")
        title_header.pack(fill="x", pady=(0, 15))
        
        # --- Секция Кошелек ---
        wallet_frame = self._create_section(main_frame, bg="#f0f0f0", border=1, relief="solid")
        self.wallet_address_var = tk.StringVar()
        
        self.wallet_label_ref = tk.Label(wallet_frame, textvariable=self.wallet_address_var, 
                                        font=("Arial", 11), bg="#f0f0f0", anchor="w")
        self.wallet_label_ref.pack(fill="x", pady=(0, 5))
        
        self._update_wallet_label_text() 
        
        edit_btn = tk.Button(wallet_frame, text="Сменить кошелек", command=self._open_custom_edit_wallet_dialog, bg="#ffffff")
        edit_btn.pack(fill="x")

        # --- Секция Баланс ---
        balance_frame = self._create_section(main_frame, bg="#e6f7ff", border=1, relief="solid", bd_color="#8ac0e6")
        tk.Label(balance_frame, text="Баланс $MEE:", font=("Arial", 10, "bold"), bg="#e6f7ff", anchor="w").pack(fill="x")
        self.mee_balance_value_label = tk.Label(balance_frame, text="0,00000000 $MEE", font=("Arial", 12), bg="#e6f7ff", anchor="w")
        self.mee_balance_value_label.pack(side="left", fill="x", expand=True)
        tk.Button(balance_frame, text="Добавить $MEE", command=lambda: self._show_modal_and_open_url("Stake", ADD_MEE_URL), 
                  bg="#1E90FF", fg="white", width=15).pack(side="right")
        
        # --- Секция Награда (Ключевая) ---
        reward_frame = self._create_section(main_frame, bg="#e6ffe6", border=1, relief="solid", bd_color="#00cc00")
        
        reward_title_frame = tk.Frame(reward_frame, bg="#e6ffe6")
        reward_title_frame.pack(fill="x")
        
        tk.Label(reward_title_frame, text="Награда (harvest):", font=("Arial", 10, "bold"), bg="#e6ffe6").pack(side="left")
        tk.Label(reward_title_frame, textvariable=self.reward_ticker_var, font=("Arial", 10, "bold"), fg="darkgreen", bg="#e6ffe6").pack(side="left", padx=5)

        reward_info_frame = tk.Frame(reward_frame, bg="#e6ffe6")
        reward_info_frame.pack(fill="x", pady=(5, 0))
        
        self.mee_reward_value_label = tk.Label(reward_info_frame, text="0,00000000 $MEE", 
                                                font=("Arial", 18, "bold"), fg="green", bg="#e6ffe6", anchor="w")
        self.mee_reward_value_label.pack(side="left", fill="x", expand=True)
        
        tk.Button(reward_info_frame, text="Забрать награду", command=lambda: self._show_modal_and_open_url("Harvest", HARVEST_BASE_URL), 
                  bg="#4CAF50", fg="white", width=15).pack(side="right")

        self.mee_rate_label = tk.Label(reward_frame, text="Скорость: 0,00 MEE/сек", font=("Arial", 8), fg="#666", bg="#e6ffe6", anchor="w")
        self.mee_rate_label.pack(fill="x", pady=(5, 0))

        # --- Секция Unstake ---
        unstake_frame = self._create_section(main_frame, bg="#ffe6e6", border=1, relief="solid", bd_color="#ff9999")
        tk.Label(unstake_frame, text="Вывод $MEE из стейкинга:", font=("Arial", 10, "bold"), bg="#ffe6e6", anchor="w").pack(side="left", fill="x", expand=True)
        tk.Button(unstake_frame, text="Забрать $MEE", command=lambda: self._show_modal_and_open_url("Unstake", UNSTAKE_BASE_URL), 
                  bg="#DC143C", fg="white", width=15).pack(side="right")

        # --- Секция Контракт ---
        contract_frame = self._create_section(main_frame, bg="#f9f9f9", border=1, relief="solid")
        tk.Label(contract_frame, text="Контракт $MEE:", font=("Arial", 8), fg="#888", bg="#f9f9f9", anchor="w").pack(fill="x")
        
        contract_display_frame = tk.Frame(contract_frame, bg="#f9f9f9")
        contract_display_frame.pack(fill="x")
        
        self.contract_value_label = tk.Label(contract_display_frame, text=MEE_COIN_T0_T1, font=("Arial", 8), bg="#f9f9f9", anchor="w", wraplength=300)
        self.contract_value_label.pack(side="left", fill="x", expand=True)
        
        tk.Button(contract_display_frame, text="Копировать", command=self._copy_contract, font=("Arial", 8), padx=5).pack(side="right")

        # --- Секция Ссылки ---
        links_frame = tk.Frame(main_frame, pady=5)
        links_frame.pack(fill="x")
        
        self._add_link_buttons(links_frame)

        # --- Секция Статус версии (Новая) ---
        self.update_status_label = tk.Label(main_frame, text="", 
                                            font=("Arial", 8), fg="#666", anchor="e")
        self.update_status_label.pack(fill="x", pady=(5, 0)) 

    def _create_section(self, parent, bg="white", border=1, relief="flat", bd_color="#eee"):
        """Создает секцию с рамкой."""
        frame = tk.Frame(parent, bg=bg, padx=10, pady=10, borderwidth=border, relief=relief, highlightbackground=bd_color, highlightthickness=1)
        frame.pack(fill="x", pady=5)
        return frame

    def _add_link_buttons(self, parent):
        """Добавляет кнопки с внешними ссылками."""
        links = [
            ("Исходный код", URL_SOURCE),
            ("Сайт", URL_SITE),
            ("График $MEE", URL_GRAPH),
            ("Обмен $MEE/$APT", URL_SWAP),
            ("Обмен $MEE/APT (2)", URL_SWAP_EARNIUM),
            ("Поддержка", URL_SUPPORT)
        ]
        
        buttons_per_row = 2
        for i, (text, url) in enumerate(links):
            row = i // buttons_per_row
            col = i % buttons_per_row
            
            btn = tk.Button(parent, text=text, command=lambda u=url: webbrowser.open_new_tab(u),
                            bg="#fffacd", fg="#333", borderwidth=1, relief="solid", 
                            highlightbackground="#ffcc00", highlightthickness=1, font=("Arial", 9, "bold"))
            
            btn.grid(row=row, column=col, sticky="nsew", padx=4, pady=4)

        parent.grid_columnconfigure(0, weight=1)
        parent.grid_columnconfigure(1, weight=1)
        
    # =======================================================
    # === 1. Функции API и расчетов (Core Logic) ===
    # =======================================================
    
    def _generate_api_urls(self, account_address):
        """Генерирует URL для запросов API."""
        if len(account_address) != 66 or not account_address.startswith("0x"):
            return None
        
        STAKE_RESOURCE_TYPE = f"0x514cfb77665f99a2e4c65a5614039c66d13e00e98daf4c86305651d29fd953e5::Staking::StakeInfo<{MEE_COIN_T0_T1},{MEE_COIN_T0_T1}>"
        STAKE_API_URL = f"{APTOS_LEDGER_URL}/accounts/{account_address}/resource/{quote(STAKE_RESOURCE_TYPE)}"

        POOL_ADDRESS = "0x482b8d35e320cca4f2d49745a1f702d052aa0366ac88e375c739dc479e81bc98"
        POOL_RESOURCE_TYPE = f"0x514cfb77665f99a2e4c65a5614039c66d13e00e98daf4c86305651d29fd953e5::Staking::PoolInfo<{MEE_COIN_T0_T1},{MEE_COIN_T0_T1}>"
        POOL_API_URL = f"{APTOS_LEDGER_URL}/accounts/{POOL_ADDRESS}/resource/{quote(POOL_RESOURCE_TYPE)}"

        return {"stakeUrl": STAKE_API_URL, "poolUrl": POOL_API_URL}

    def _fetch_data(self, api_url):
        """Выполняет запрос к Aptos API."""
        try:
            response = requests.get(api_url, timeout=5)
            if response.status_code == 404:
                if "StakeInfo" in api_url:
                    return {"amount": "0", "reward_amount": "0", "reward_debt": "0"}
                return None 
            response.raise_for_status()
            data = response.json()
            return data.get("data")
        except requests.exceptions.RequestException:
            return None

    def _fetch_ledger_timestamp(self):
        """Получает текущую временную метку из Ledger."""
        try:
            response = requests.get(APTOS_LEDGER_URL, timeout=5)
            response.raise_for_status()
            data = response.json()
            return int(data["ledger_timestamp"]) // 1000000
        except Exception:
            return None

    def _calculate_rate_per_second(self, stake_data, pool_data):
        """Рассчитывает ставку накопления MEE в секунду."""
        try:
            amount = int(stake_data["amount"]) * RAW_DATA_CORRECTION_FACTOR
            if amount == 0:
                return 0.0

            token_per_second = int(pool_data["token_per_second"])
            unlocking_amount = int(pool_data["unlocking_amount"])
            staked_value = int(pool_data["staked_coins"]["value"])
            pool_total_amount = staked_value - unlocking_amount
            
            if pool_total_amount <= 0: 
                return 0.0
            
            RATE_PRECISION = 10**18 
            
            numerator_for_rate = token_per_second * amount * RATE_PRECISION
            rate_raw_bigint = numerator_for_rate // pool_total_amount
            
            rate_float_raw = rate_raw_bigint / RATE_PRECISION
            
            rate_mee_per_sec = rate_float_raw / (10 ** DECIMALS) 
            
            return rate_mee_per_sec
        except Exception:
            return 0.0

    def _calculate_stake_reward(self, stake_data, pool_data, current_time):
        """Рассчитывает текущий баланс стейкинга и общую награду."""
        if not stake_data or not pool_data or current_time is None:
            return None, None

        CORRECT_FACTOR = RAW_DATA_CORRECTION_FACTOR

        try:
            amount = int(stake_data["amount"]) * CORRECT_FACTOR
            reward_amount = int(stake_data["reward_amount"]) * CORRECT_FACTOR
            reward_debt = int(stake_data["reward_debt"]) * CORRECT_FACTOR
            
            if amount == 0:
                return 0.0, 0.0

            acc_reward_per_share = int(pool_data["acc_reward_per_share"])
            token_per_second = int(pool_data["token_per_second"])
            last_reward_time = int(pool_data["last_reward_time"])
            unlocking_amount = int(pool_data["unlocking_amount"])
            staked_value = int(pool_data["staked_coins"]["value"])
            
            pool_total_amount = staked_value - unlocking_amount
            passed_seconds = current_time - last_reward_time
            
            reward_per_share = 0
            if pool_total_amount > 0 and passed_seconds > 0:
                reward_per_share = (token_per_second * passed_seconds * ACC_PRECISION) // pool_total_amount
            
            new_acc = acc_reward_per_share + reward_per_share
            pending = (amount * new_acc // ACC_PRECISION) - reward_debt
            total_reward_raw = reward_amount + pending
            
            stake_balance = amount / (10 ** DECIMALS) 
            
            total_reward_float = total_reward_raw / (10 ** DECIMALS)
            
            return stake_balance, total_reward_float
        except Exception:
            return None, None
            
    # =======================================================
    # === 2. Функции управления данными и GUI ===
    # =======================================================

    def _load_wallet_address(self):
        """Загружает адрес кошелька из файла."""
        try:
            if os.path.exists(WALLET_FILE):
                with open(WALLET_FILE, 'r') as f:
                    address = f.read().strip()
                    if len(address) == 66 and address.startswith("0x"):
                        return address
            
            self._save_wallet_address(DEFAULT_EXAMPLE_ADDRESS)
            return DEFAULT_EXAMPLE_ADDRESS
        except Exception:
            return DEFAULT_EXAMPLE_ADDRESS

    def _save_wallet_address(self, address):
        """Сохраняет адрес кошелька в файл."""
        try:
            with open(WALLET_FILE, 'w') as f:
                f.write(address)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить адрес кошелька в файл: {e}")

    def _open_custom_edit_wallet_dialog(self):
        """Кастомное окно для смены кошелька с поддержкой Ctrl+V."""
        top = tk.Toplevel(self.master)
        top.title("Сменить кошелек")
        top.geometry("480x180")
        top.transient(self.master)
        top.grab_set()
        
        result_address = tk.StringVar(value=self.current_wallet_address)
        
        tk.Label(top, text="Введите новый адрес кошелька (66 символов, 0x...):", 
                 font=("Arial", 10, "bold"), pady=10).pack(pady=(10, 5))
        
        address_entry = tk.Entry(top, textvariable=result_address, width=50, font=("Arial", 10))
        address_entry.pack(pady=5)
        
        def force_paste(event=None):
            try:
                content = top.clipboard_get()
                address_entry.delete(0, tk.END)
                address_entry.insert(0, content.strip())
            except tk.TclError:
                pass
            return "break"
            
        address_entry.bind('<Control-v>', force_paste)
        address_entry.bind('<Control-V>', force_paste) 
        
        address_entry.focus_set()
        address_entry.selection_range(0, tk.END)

        def save_address():
            top.address = result_address.get()
            top.destroy()
        
        def cancel():
            top.address = None
            top.destroy()
            
        btn_frame = tk.Frame(top)
        btn_frame.pack(pady=10)
        
        tk.Button(btn_frame, text="Сохранить", command=save_address, bg="#4CAF50", fg="white", width=12).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Отмена", command=cancel, bg="#DC143C", fg="white", width=12).pack(side=tk.LEFT, padx=5)
        
        top.protocol("WM_DELETE_WINDOW", cancel)
        top.bind('<Return>', lambda e: save_address())
        top.bind('<Escape>', lambda e: cancel())

        self.master.update_idletasks()
        # Центрируем модальное окно относительно главного окна
        x = self.master.winfo_x() + (self.master.winfo_width() // 2) - (top.winfo_width() // 2)
        y = self.master.winfo_y() + (self.master.winfo_height() // 2) - (top.winfo_height() // 2)
        top.geometry(f'+{x}+{y}')
        
        top.wait_window(top)

        new_address = getattr(top, 'address', None)

        if new_address is not None:
            trimmed_address = new_address.strip()
            if len(trimmed_address) == 66 and trimmed_address.startswith("0x"):
                self.current_wallet_address = trimmed_address
                self._save_wallet_address(trimmed_address)
                
                self._show_custom_info_modal("Обновление", "Адрес кошелька сохранен. Запускается обновление данных...")
                
                if self.simulation_job:
                    self.master.after_cancel(self.simulation_job)
                    self.simulation_job = None
                self.is_running = False
                self.mee_current_reward = 0.0
                self.mee_rate_per_sec = 0.0
                self._update_reward_labels() 
                self.run_update_in_thread()
            elif trimmed_address:
                messagebox.showerror("Ошибка", "Неверный формат адреса кошелька. Должен быть 66 символов и начинаться с 0x.")

    def _show_custom_info_modal(self, title, message):
        """Информационное окно."""
        top = tk.Toplevel(self.master)
        top.title(title)
        top.geometry("480x200") 
        top.transient(self.master)
        top.grab_set()
        
        tk.Label(top, text=title, font=("Arial", 12, "bold"), pady=10, fg="#1E90FF").pack(pady=(10, 5))
        tk.Label(top, text=message, justify=tk.LEFT, padx=10, wraplength=450).pack(pady=5, padx=10) 
        
        ok_button = tk.Button(top, text="ОК", command=top.destroy, width=10, bg="#4CAF50", fg="white")
        ok_button.pack(pady=15)
        top.bind('<Return>', lambda e: top.destroy())
        
        self.master.update_idletasks()
        x = self.master.winfo_x() + (self.master.winfo_width() // 2) - (top.winfo_width() // 2)
        y = self.master.winfo_y() + (self.master.winfo_height() // 2) - (top.winfo_height() // 2)
        top.geometry(f'+{x}+{y}')
        top.wait_window(top)

    def _show_confirmation_modal(self, title, message):
        """Подтверждающее окно."""
        top = tk.Toplevel(self.master)
        top.title(title)
        top.geometry("480x280") 
        top.transient(self.master)
        top.grab_set()
        
        result = tk.BooleanVar(value=False) 

        def open_browser_and_close():
            result.set(True)
            top.destroy()
            
        def close_window():
            result.set(False)
            top.destroy()
        
        tk.Label(top, text=title, font=("Arial", 12, "bold"), pady=10, fg="#1E90FF").pack(pady=(10, 5))
        tk.Label(top, text=message, justify=tk.LEFT, padx=10, wraplength=450).pack(pady=5, padx=10) 
        
        ok_button = tk.Button(top, text="Открыть браузер", command=open_browser_and_close, 
                              width=25, bg="#4CAF50", fg="white", font=("Arial", 10, "bold"))
        ok_button.pack(pady=15)
        
        top.bind('<Return>', lambda e: open_browser_and_close())
        top.bind('<Escape>', lambda e: close_window())
        top.protocol("WM_DELETE_WINDOW", close_window) 

        self.master.update_idletasks()
        x = self.master.winfo_x() + (self.master.winfo_width() // 2) - (top.winfo_width() // 2)
        y = self.master.winfo_y() + (self.master.winfo_height() // 2) - (top.winfo_height() // 2)
        top.geometry(f'+{x}+{y}')

        top.wait_window(top) 
        
        return result.get()

    def _show_update_modal(self, new_version, download_url):
        """Модальное окно с предложением обновить программу."""
        top = tk.Toplevel(self.master)
        top.title("Доступно обновление!")
        top.geometry("480x240")
        top.transient(self.master)
        top.grab_set()
        
        tk.Label(top, text=f"🎉 Есть новая версия: v{new_version}!", 
                 font=("Arial", 12, "bold"), pady=10, fg="green").pack(pady=(10, 5))
        
        tk.Label(top, text=f"Ваша текущая версия: v{CURRENT_VERSION}\n"
                           f"Нажмите \"Скачать\" для перехода на страницу релиза.", 
                 justify=tk.CENTER, padx=10).pack(pady=5, padx=10)
        
        def open_and_close():
            webbrowser.open_new_tab(download_url)
            top.destroy()

        btn_frame = tk.Frame(top)
        btn_frame.pack(pady=15)
        
        tk.Button(btn_frame, text="Скачать", command=open_and_close, 
                  width=25, bg="#ffcc00", fg="#333", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=5)
        
        tk.Button(btn_frame, text="Позже", command=top.destroy, width=10).pack(side=tk.LEFT, padx=5)

        top.bind('<Return>', lambda e: open_and_close())
        top.bind('<Escape>', lambda e: top.destroy())
        top.protocol("WM_DELETE_WINDOW", top.destroy)

        self.master.update_idletasks()
        x = self.master.winfo_x() + (self.master.winfo_width() // 2) - (top.winfo_width() // 2)
        y = self.master.winfo_y() + (self.master.winfo_height() // 2) - (top.winfo_height() // 2)
        top.geometry(f'+{x}+{y}')

        top.wait_window(top) 

    def _update_wallet_label_text(self):
        """Обновляет текст и цвет метки кошелька."""
        address = self.current_wallet_address
        display_address = f"{address[:6]}...{address[-4:]}"
        
        if address == DEFAULT_EXAMPLE_ADDRESS:
            display_text = f"Кошелек: {display_address} (ПРИМЕР)"
            color = "darkorange"
        else:
            display_text = f"Кошелек: {display_address}"
            color = "purple"
            
        self.wallet_address_var.set(display_text)
        
        if self.wallet_label_ref:
             self.wallet_label_ref.config(fg=color) 

    def _update_labels(self, results):
        """Обновляет все метки GUI после получения данных."""
        mee_balance = results.get("meeBalance")
        mee_total_reward_float = results.get("meeTotalRewardFloat")
        mee_rate = results.get("meeRate")
        
        self._update_wallet_label_text()
        
        if mee_balance is None or mee_total_reward_float is None:
            self.mee_balance_value_label.config(text='Ошибка! Проверьте адрес или сеть.', fg="red")
            self.mee_reward_value_label.config(text='Ошибка! Проверьте адрес или сеть.', fg="red")
            self.mee_rate_label.config(text="Скорость: Ошибка")
            self.reward_ticker_var.set("[ОШИБКА]")
            self.is_running = False
            return
        
        self.mee_rate_per_sec = mee_rate
        self.mee_current_reward = mee_total_reward_float
        
        balance_str = f"{mee_balance:,.8f} $MEE".replace(",", " ").replace(".", ",")
        self.mee_balance_value_label.config(text=balance_str, fg="black")

        rate_str = f"{self.mee_rate_per_sec:,.12f} MEE/сек".replace(",", " ").replace(".", ",")
        self.mee_rate_label.config(text=f"Скорость: {rate_str}")
        
        self._update_reward_labels()

        self.is_running = True
        self.countdown_val = UPDATE_INTERVAL_SECONDS
        if not self.simulation_job:
            self.run_periodic_tasks() 

    def _update_reward_labels(self):
        """Обновляет только метки награды (симуляция)."""
        mee_reward_str = f"{self.mee_current_reward:,.8f} $MEE".replace(",", " ").replace(".", ",")
        self.mee_reward_value_label.config(text=mee_reward_str, fg="green")
        self.reward_ticker_var.set(self.animation_frames[self.current_frame_index])


    def _fetch_and_calculate_rewards(self):
        """Основная функция для запроса данных (выполняется в потоке)."""
        urls = self._generate_api_urls(self.current_wallet_address)
        if not urls: 
            return {"meeBalance": None, "meeTotalRewardFloat": None, "meeRate": 0.0}
        
        current_time = self._fetch_ledger_timestamp()
        
        mee_stake_data = self._fetch_data(urls["stakeUrl"])
        mee_pool_data = self._fetch_data(urls["poolUrl"])

        if not mee_stake_data or not mee_pool_data or current_time is None:
            return {"meeBalance": None, "meeTotalRewardFloat": None, "meeRate": 0.0}

        stake_balance, total_reward_float = self._calculate_stake_reward(
            mee_stake_data, mee_pool_data, current_time
        )
        
        mee_rate = self._calculate_rate_per_second(mee_stake_data, mee_pool_data)

        return {
            "meeBalance": stake_balance, 
            "meeTotalRewardFloat": total_reward_float, 
            "meeRate": mee_rate
        }

    def run_update_in_thread(self):
        """Запускает обновление данных в отдельном потоке."""
        def target():
            results = self._fetch_and_calculate_rewards()
            self.master.after(0, lambda: self._update_labels(results)) 
        
        threading.Thread(target=target).start()

    def run_periodic_tasks(self):
        """Цикл, управляющий симуляцией роста награды и невидимым 60-секундным таймером."""
        if not self.is_running:
            return
            
        self.mee_current_reward += self.mee_rate_per_sec
        self.current_frame_index = (self.current_frame_index + 1) % len(self.animation_frames)

        self._update_reward_labels() 

        self.countdown_val -= 1
        
        if self.countdown_val <= 0:
            self.run_update_in_thread() 
            self.countdown_val = UPDATE_INTERVAL_SECONDS 

        self.simulation_job = self.master.after(1000, self.run_periodic_tasks) 
        
    def _start_app(self):
        """Начало работы приложения: запуск монитора и проверки обновлений."""
        self.run_update_in_thread()
        self._run_update_check_in_thread(manual_check=False)
    
    # =======================================================
    # === 3. Интерактивная Проверка Обновлений ===
    # =======================================================

    def _set_update_status(self, text, fg_color="#666", is_clickable=False, click_action=None):
        """Устанавливает статус, цвет и управляет кликабельностью метки."""
        self.update_status_label.config(text=text, fg=fg_color, font=("Arial", 8, "bold" if fg_color == "red" or fg_color == "darkgreen" else "normal"))
        
        # Сначала очищаем все привязки
        self.update_status_label.unbind("<Enter>")
        self.update_status_label.unbind("<Leave>")
        self.update_status_label.unbind("<Button-1>")

        if is_clickable:
            # Делаем кликабельность визуально очевидной
            self.update_status_label.bind("<Enter>", lambda e: self.update_status_label.config(fg="#1E90FF", cursor="hand2"))
            self.update_status_label.bind("<Leave>", lambda e: self.update_status_label.config(fg=fg_color, cursor=""))
            if click_action:
                self.update_status_label.bind("<Button-1>", click_action)

    def _manual_update_check(self):
        """Обработчик клика: запускает проверку обновления и меняет статус."""
        # Устанавливаем статус, показывающий, что проверка началась
        self._set_update_status(f"Версия v{CURRENT_VERSION} [Проверка обновлений...]", fg_color="#666", is_clickable=False)
        # Запускаем проверку в отдельном потоке
        self._run_update_check_in_thread(manual_check=True)

    def _run_update_check_in_thread(self, manual_check=False):
        """Запускает проверку обновлений в отдельном потоке."""
        
        if not manual_check:
             # Статус при автопроверке
             self._set_update_status(f"Версия v{CURRENT_VERSION} [Проверка обновлений...]", fg_color="#666")
        
        def target():
            new_version, download_url = self.update_checker.fetch_latest_release()
            
            # Вернуться в главный поток Tkinter для работы с GUI
            self.master.after(0, lambda: self._handle_update_result(new_version, download_url, manual_check)) 

        threading.Thread(target=target).start()

    def _handle_update_result(self, new_version, download_url, manual_check=False):
        """Обрабатывает результат проверки обновлений в главном потоке."""
        
        if new_version and download_url:
            # 1. Есть новая версия
            text = f"НОВАЯ ВЕРСИЯ v{new_version} ДОСТУПНА! (Нажмите для скачивания)"
            self._set_update_status(text, fg_color="red", is_clickable=True, 
                                    click_action=lambda e: self._show_update_modal(new_version, download_url))
            self._show_update_modal(new_version, download_url)
            
        elif new_version is False:
            # 2. Ошибка проверки
            text = f"Версия v{CURRENT_VERSION} [Ошибка проверки. Нажмите для повтора.]"
            self._set_update_status(text, fg_color="red", is_clickable=True, 
                                    click_action=lambda e: self._manual_update_check())
        else:
            # 3. Последняя версия
            if manual_check:
                # Результат ручной проверки
                text = f"Версия v{CURRENT_VERSION} (У вас самая последняя версия)"
                self._set_update_status(text, fg_color="darkgreen") 
            else:
                # Результат автопроверки (делаем кликабельным)
                text = f"Версия v{CURRENT_VERSION} (Последняя. Проверить обновление.)"
                self._set_update_status(text, fg_color="#666", is_clickable=True, 
                                        click_action=lambda e: self._manual_update_check())


    # =======================================================
    # === 4. Функции обработчиков ===
    # =======================================================
    
    def _copy_contract(self):
        """Копирует контракт MEE в буфер обмена."""
        try:
            self.master.clipboard_clear()
            self.master.clipboard_append(MEE_COIN_T0_T1)
            self.master.update()
            self._show_custom_info_modal("Копирование", "Контракт $MEE успешно скопирован в буфер обмена!")
        except Exception:
             messagebox.showerror("Ошибка", "Не удалось скопировать контракт в буфер обмена.")

    def _show_modal_and_open_url(self, action, url):
        """Показывает модальное окно с инструкциями и открывает URL только после подтверждения."""
        
        instructions = {
            "Harvest": {
                "title": "✅ Контракт скопирован! Откройте страницу Harvest.",
                "text": "1. Подключите кошелек.\n2. Вставьте контракт $MEE (он уже в буфере обмена) в поля T0 и T1.\n3. Нажмите RUN и подпишите транзакцию."
            },
            "Stake": {
                "title": "✅ Контракт скопирован! Откройте страницу Stake.",
                "text": "1. Подключите кошелек.\n2. Вставьте контракт $MEE в поля T0 и T1.\n3. В поле \"arg0: u64\" введите сумму $MEE для внесения, используя формат без десятичных знаков (1 MEE = 1000000).\n4. Нажмите RUN и подпишите транзакцию."
            },
            "Unstake": {
                "title": "⚠️ Готовы забрать $MEE из стейкинга?",
                "text": "1. Контракт скопирован! Подключите кошелек.\n2. Вставьте контракт $MEE в поля T0 и T1.\n3. В поле \"arg0: u64\" введите сумму $MEE, которую хотите забрать (с +6 нулями).\n4. В поле \"arg1: u8\" введите тип вывода: 0 (Обычный) или 1 (Мгновенный, комиссия 15%).\n5. Нажмите RUN и подпишите транзакцию."
            }
        }
        
        data = instructions.get(action, {"title": "Переход", "text": "Контракт скопирован."})
        
        self.master.clipboard_clear()
        self.master.clipboard_append(MEE_COIN_T0_T1)
        self.master.update()
        
        user_clicked_open = self._show_confirmation_modal(data["title"], data["text"])
        
        if user_clicked_open:
            webbrowser.open_new_tab(url)

# --- Запуск ---
if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = MeeiroApp(master=root)
        root.protocol("WM_DELETE_WINDOW", root.destroy) 
        app.mainloop()
    except Exception as e:
        print(f"Критическая ошибка приложения: {e}")
        messagebox.showerror("Критическая ошибка", f"Произошла непредвиденная ошибка: {e}")
