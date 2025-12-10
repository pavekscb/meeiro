import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
import requests
import json
import threading 
import time
from urllib.parse import quote 
import webbrowser
import os 

# --- Файл и Константы для адреса кошелька ---
WALLET_FILE = "WALLET_ADDRESS.txt"
# Адрес для примера, который будет сохранен, если файл отсутствует
DEFAULT_EXAMPLE_ADDRESS = "0x9ba27fc8a65ba4507fc4cca1b456e119e4730b8d8cfaf72a2a486e6d0825b27b"
WALLET_NOT_SET = "0x0" * 33 # Специальное значение для внутреннего контроля (например, если сохранить не удалось)

# --- Константы ---
DECIMALS = 8 
ACC_PRECISION = 100000000000 # 10^11
UPDATE_INTERVAL_SECONDS = 60 
LEDGER_URL = "https://fullnode.mainnet.aptoslabs.com/v1"
HARVEST_BASE_URL = "https://explorer.aptoslabs.com/account/0x514cfb77665f99a2e4c65a5614039c66d13e00e98daf4c86305651d29fd953e5/modules/run/Staking/harvest?network=mainnet"

# ОБНОВЛЕННЫЕ ССЫЛКИ
TELEGRAM_SUPPORT_URL = "https://t.me/cripto_karta" 
GITHUB_SOURCE_URL = "https://github.com/pavekscb/meeiro" 

# Основной контракт монеты MEE
MEE_COIN_T0_T1 = "0xe9c192ff55cffab3963c695cff6dbf9dad6aff2bb5ac19a6415cad26a81860d9::mee_coin::MeeCoin"
# Список популярных кошельков Aptos
APTOS_WALLETS = "Petra Wallet, Martian Wallet, Pontem Wallet"

# Ссылка для добавления стейкинга MEE
ADD_MEE_URL = "https://explorer.aptoslabs.com/account/0x514cfb77665f99a2e4c65a5614039c66d13e00e98daf4c86305651d29fd953e5/modules/run/Staking/stake?network=mainnet"


# --- Функции для работы с адресом кошелька и API URL ---

def save_wallet_address(address):
    """Сохраняет адрес кошелька в файл."""
    with open(WALLET_FILE, 'w') as f:
        f.write(address)

def load_wallet_address():
    """Загружает адрес кошелька из файла, или создает его с примером (DEFAULT_EXAMPLE_ADDRESS)."""
    if os.path.exists(WALLET_FILE):
        try:
            with open(WALLET_FILE, 'r') as f:
                address = f.read().strip()
            # Проверяем, что адрес валиден (66 символов, начинается с 0x)
            if len(address) == 66 and address.startswith("0x"):
                return address # Валидный сохраненный адрес
        except Exception:
            pass # Если чтение не удалось, идем к установке по умолчанию
    
    # Если файл не существует, содержимое некорректно, или чтение не удалось:
    try:
        save_wallet_address(DEFAULT_EXAMPLE_ADDRESS)
        return DEFAULT_EXAMPLE_ADDRESS # Возвращаем адрес для примера
    except Exception:
        # Резервный вариант, если сохранить даже пример не удалось
        return WALLET_NOT_SET

def generate_api_urls(account_address):
    """Генерирует API URL для MEE Coin Staking на основе адреса кошелька."""
    
    if len(account_address) != 66 or not account_address.startswith("0x"):
        return None, None 

    STAKE_RESOURCE_TYPE = "0x514cfb77665f99a2e4c65a5614039c66d13e00e98daf4c86305651d29fd953e5::Staking::StakeInfo<0xe9c192ff55cffab3963c695cff6dbf9dad6aff2bb5ac19a6415cad26a81860d9::mee_coin::MeeCoin,0xe9c192ff55cffab3963c695cff6dbf9dad6aff2bb5ac19a6415cad26a81860d9::mee_coin::MeeCoin>"
    STAKE_API_URL = f"https://fullnode.mainnet.aptoslabs.com/v1/accounts/{account_address}/resource/{quote(STAKE_RESOURCE_TYPE, safe=':<>,' )}"

    POOL_ADDRESS = "0x482b8d35e320cca4f2d49745a1f702d052aa0366ac88e375c739dc479e81bc98"
    POOL_RESOURCE_TYPE = "0x514cfb77665f99a2e4c65a5614039c66d13e00e98daf4c86305651d29fd953e5::Staking::PoolInfo<0xe9c192ff55cffab3963c695cff6dbf9dad6aff2bb5ac19a6415cad26a81860d9::mee_coin::MeeCoin,0xe9c192ff55cffab3963c695cff6dbf9dad6aff2bb5ac19a6415cad26a81860d9::mee_coin::MeeCoin>"
    POOL_API_URL = f"https://fullnode.mainnet.aptoslabs.com/v1/accounts/{POOL_ADDRESS}/resource/{quote(POOL_RESOURCE_TYPE, safe=':<>,' )}"

    return STAKE_API_URL, POOL_API_URL

# Инициализация глобальных URL
ACCOUNT_ADDRESS = load_wallet_address()
STAKE_API_URL, POOL_API_URL = generate_api_urls(ACCOUNT_ADDRESS)


# --- Функции для работы с данными ---
def fetch_ledger_timestamp():
    """Получает текущее время из Aptos ledger."""
    try:
        response = requests.get(LEDGER_URL, timeout=5) 
        response.raise_for_status()
        data = response.json()
        return int(data['ledger_timestamp']) // 1000000 
    except Exception as e:
        return None

def fetch_data(api_url):
    """Общая функция для получения данных StakeInfo или PoolInfo."""
    try:
        response = requests.get(api_url, timeout=5)
        response.raise_for_status()
        return response.json()['data']
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            if api_url == STAKE_API_URL:
                return {'amount': 0, 'reward_amount': 0, 'reward_debt': 0}
            return None
        return None
    except Exception as e:
        return None

def fetch_mee_stake_data():
    """Получает данные о стейкинге MEE Coin."""
    global STAKE_API_URL
    if STAKE_API_URL is None: return None
    data = fetch_data(STAKE_API_URL)
    if data is None: return None
    if isinstance(data, dict) and 'amount' in data:
        return {
            'amount': int(data['amount']),
            'reward_amount': int(data['reward_amount']),
            'reward_debt': int(data['reward_debt'])
        }
    return None

def fetch_mee_pool_data():
    """Получает данные о пуле MEE Coin Staking."""
    global POOL_API_URL
    if POOL_API_URL is None: return None
    data = fetch_data(POOL_API_URL)
    if data is None: return None
    return {
        'acc_reward_per_share': int(data['acc_reward_per_share']),
        'token_per_second': int(data['token_per_second']),
        'last_reward_time': int(data['last_reward_time']),
        'unlocking_amount': int(data['unlocking_amount']),
        'staked_value': int(data.get('staked_coins', {}).get('value', 0))
    }


def calculate_rate_per_second(stake_data, pool_data):
    """Рассчитывает скорость генерации награды в $MEE в секунду."""
    if stake_data is None or pool_data is None or stake_data.get('amount', 0) == 0:
        return 0.0

    amount = stake_data['amount'] 
    token_per_second = pool_data['token_per_second'] 
    unlocking_amount = pool_data['unlocking_amount']
    staked_value = pool_data['staked_value']
    
    pool_total_amount = staked_value - unlocking_amount
    
    if pool_total_amount <= 0:
        return 0.0
        
    rate_raw = (token_per_second * amount) / pool_total_amount
    rate_mee = rate_raw / (10 ** DECIMALS)
    
    return rate_mee * 100 


def calculate_stake_reward(stake_data, pool_data, current_time):
    """
    Рассчитывает баланс стейкинга и полную награду.
    Возвращает (stake_balance, total_reward)
    """
    if stake_data is None or pool_data is None or current_time is None:
        return None, None
    
    amount = stake_data['amount']
    reward_amount = stake_data['reward_amount']
    reward_debt = stake_data['reward_debt']
    
    if amount == 0:
        return 0.0, 0.0

    acc_reward_per_share = pool_data['acc_reward_per_share']
    token_per_second = pool_data['token_per_second']
    last_reward_time = pool_data['last_reward_time']
    unlocking_amount = pool_data['unlocking_amount']
    staked_value = pool_data['staked_value']
    
    pool_total_amount = staked_value - unlocking_amount
    passed_seconds = current_time - last_reward_time
    
    reward_per_share = 0
    if pool_total_amount != 0 and passed_seconds > 0:
        reward_per_share = (token_per_second * passed_seconds * ACC_PRECISION) // pool_total_amount
    
    new_acc = acc_reward_per_share + reward_per_share
    pending = (amount * new_acc // ACC_PRECISION) - reward_debt
    total_reward_raw = reward_amount + pending
    
    stake_balance = amount / (10 ** DECIMALS)
    total_reward = total_reward_raw / (10 ** DECIMALS)
    
    return stake_balance, total_reward


def get_all_rewards():
    """Объединяет получение данных, расчеты награды и ставок только для MEE Coin Staking."""
    global ACCOUNT_ADDRESS
    if len(ACCOUNT_ADDRESS) != 66 or not ACCOUNT_ADDRESS.startswith("0x"):
        return None, None, 0.0 
        
    current_time = fetch_ledger_timestamp()
    
    # 1. MEE Coin Staking
    mee_stake_data = fetch_mee_stake_data()
    mee_pool_data = fetch_mee_pool_data()
    
    if mee_stake_data is None or mee_pool_data is None:
        return None, None, 0.0

    mee_balance, mee_total_reward = calculate_stake_reward(
        mee_stake_data, mee_pool_data, current_time
    )
    mee_rate = calculate_rate_per_second(mee_stake_data, mee_pool_data)

    return mee_balance, mee_total_reward, mee_rate

# --- Функции для GUI (MeeiroApp) ---

def open_url(url):
    """Открывает URL во внешнем браузере."""
    webbrowser.open_new_tab(url)

class MeeiroApp:
    def __init__(self, master):
        self.master = master
        master.title("Майнинг MEEIRO ($MEE)")
        
        # УМЕНЬШЕНА НАЧАЛЬНАЯ ВЫСОТА ОКНА (380)
        self.center_window(980, 380) 
        master.resizable(True, True) 
        master.configure(bg="#f0f0f0") 

        self.countdown_val = UPDATE_INTERVAL_SECONDS
        self.current_wallet = ACCOUNT_ADDRESS
        self.is_running = (len(self.current_wallet) == 66 and self.current_wallet.startswith("0x"))
        self.simulation_job = None
        
        self.mee_current_reward = 0.0
        self.mee_rate_per_sec = 0.0

        # --- 1. Фрейм для отображения адреса кошелька, кнопок Изменить/Исходный код/Поддержка ---
        self.wallet_frame = tk.Frame(master, bg="#f0f0f0")
        self.wallet_frame.pack(pady=(5, 0), fill='x', padx=10) 
        
        # --- Кнопка "Поддержка" (КРАЙНИЙ ПРАВЫЙ) ---
        support_btn = tk.Button(self.wallet_frame, text="Поддержка 💬", 
                                command=lambda: open_url(TELEGRAM_SUPPORT_URL), 
                                font=("Arial", 9, "bold"), bg="#0088CC", fg="white", activebackground="#007acc")
        support_btn.pack(side=tk.RIGHT) 

        # --- Кнопка "Исходный код" (ПЕРЕД Поддержкой) ---
        source_btn = tk.Button(self.wallet_frame, text="Исходный код 🔗", 
                                command=lambda: open_url(GITHUB_SOURCE_URL), 
                                font=("Arial", 9, "bold"), bg="#333333", fg="white", activebackground="#222222")
        source_btn.pack(side=tk.RIGHT, padx=(0, 5)) 

        # --- Данные Кошелька (ЛЕВЫЕ) ---
        tk.Label(self.wallet_frame, text="Кошелек:", font=("Arial", 10), bg="#f0f0f0").pack(side=tk.LEFT)
        self.wallet_label = tk.Label(self.wallet_frame, text="Не установлен", font=("Arial", 10, "bold"), fg="red", bg="#f0f0f0")
        self.wallet_label.pack(side=tk.LEFT, padx=(5, 5))
        edit_btn = tk.Button(self.wallet_frame, text="Изменить", command=self.open_edit_wallet_dialog, font=("Arial", 8))
        edit_btn.pack(side=tk.LEFT)
        
        # Сообщение о статусе
        self.status_message = tk.Label(master, text="", font=("Arial", 11, "italic"), fg="red", bg="#f0f0f0")
        self.status_message.pack(pady=(3, 0)) 
        
        # Разделитель
        ttk.Separator(master, orient='horizontal').pack(fill='x', pady=3, padx=10)


        # --- 2. Секция MEE Coin Staking (MEE -> MEE) ---

        self.mee_balance_frame = tk.Frame(master, bg="#f0f0f0")
        self.mee_balance_frame.pack(pady=3) 
        # Баланс
        tk.Label(self.mee_balance_frame, text="Баланс $MEE:", font=("Arial", 14), bg="#f0f0f0").pack(side=tk.LEFT)
        self.mee_balance_value_label = tk.Label(self.mee_balance_frame, text="Ожидание...", font=("Arial", 14, "bold"), fg="black", bg="#f0f0f0")
        self.mee_balance_value_label.pack(side=tk.LEFT, padx=(5, 10))
        
        # Кнопка "Добавить $MEE" (ОРАНЖЕВЫЙ)
        tk.Button(self.mee_balance_frame, text="Добавить $MEE", command=lambda: open_url(ADD_MEE_URL), font=("Arial", 9, "bold"), 
                  bg="#FF9800", fg="white", activebackground="#e68a00").pack(side=tk.LEFT, padx=5)
        
        # Награда MEE Coin
        self.mee_reward_frame = tk.Frame(master, bg="#f0f0f0")
        self.mee_reward_frame.pack(pady=(0, 5)) # Уменьшен отступ
        # Награда
        tk.Label(self.mee_reward_frame, text="Награда (harvest):", font=("Arial", 12), bg="#f0f0f0").pack(side=tk.LEFT, padx=(0, 5)) 
        self.mee_reward_value_label = tk.Label(self.mee_reward_frame, text="Ожидание...", font=("Arial", 12, "bold"), fg="green", bg="#f0f0f0")
        self.mee_reward_value_label.pack(side=tk.LEFT, padx=(0, 10)) 

        # Кнопка "Забрать награду" (ЗЕЛЕНЫЙ) - С КОПИРОВАНИЕМ
        tk.Button(self.mee_reward_frame, text="Забрать награду", command=self.harvest_and_copy, font=("Arial", 10, "bold"), 
                  bg="#4CAF50", fg="white", activebackground="#45a049").pack(side=tk.LEFT)
        
        # Разделитель
        ttk.Separator(master, orient='horizontal').pack(fill='x', pady=5, padx=10)
        
        # --- 3. Контракт и инструкции ---
        
        self.contract_frame = tk.Frame(master, bg="#f0f0f0")
        self.contract_frame.pack(pady=(5, 5), padx=10, fill='x') 
        
        tk.Label(self.contract_frame, text="Контракт $MEE:", font=("Arial", 11, "bold"), bg="#f0f0f0").pack(side=tk.LEFT)
        
        # НОВАЯ ПОЗИЦИЯ МЕТКИ ОПОВЕЩЕНИЯ О КОПИРОВАНИИ
        self.copy_notification_label = tk.Label(self.contract_frame, text="", font=("Arial", 9, "italic"), width=15, bg="#f0f0f0", anchor='w')
        self.copy_notification_label.pack(side=tk.LEFT, padx=(5, 5))
        
        # Кнопка "Копировать" (Справа)
        copy_btn = tk.Button(self.contract_frame, text="Копировать", font=("Arial", 9), 
                             command=lambda: self.copy_to_clipboard(MEE_COIN_T0_T1, self.copy_notification_label),
                             bg="#2196F3", fg="white", activebackground="#1e88e5")
        copy_btn.pack(side=tk.RIGHT) 

        # Поле для контракта (Растягивается между уведомлением и кнопкой)
        self.contract_value_entry = tk.Entry(self.contract_frame, 
                                            textvariable=tk.StringVar(self.contract_frame, value=MEE_COIN_T0_T1), 
                                            state='readonly', 
                                            font=("Consolas", 10), relief=tk.FLAT, bd=2, bg="#FFFFFF")
        # expand=True, fill='x' гарантируют растягивание
        self.contract_value_entry.pack(side=tk.LEFT, padx=(5, 5), expand=True, fill='x')
        
        
        # --- 4. Подсказки (Стилизация LabelFrame) ---
        
        self.tips_frame = tk.LabelFrame(master, text=" Полезная информация ", font=("Arial", 10, "bold"), padx=10, pady=5, bg="#FFFFFF", fg="#333333")
        self.tips_frame.pack(pady=10, padx=20, fill='both', expand=True) 

        # Подсказка 1: Добавление токена в кошелек
        tip1_text = (f"💳 Добавление $MEE в кошелек:\n"
                     f"Монета $MEE на блокчейне Aptos. Чтобы увидеть её баланс, скопируйте контракт "
                     f"выше и добавьте актив вручную в вашем кошельке. "
                     f"Поддерживаемые кошельки: {APTOS_WALLETS}.")
        # wraplength увеличена для широкого окна
        tk.Label(self.tips_frame, text=tip1_text, font=("Arial", 9), justify=tk.LEFT, wraplength=900, fg="#333333", bg="#FFFFFF").pack(pady=(5, 2), anchor='w')
        
        ttk.Separator(self.tips_frame, orient='horizontal').pack(fill='x', pady=5)


        # Подсказка 2: Сбор награды (Harvest)
        tip2_text = (f"💰 Сбор награды (Harvest):\n"
                     f"Нажмите 'Забрать награду', **контракт $MEE автоматически скопируется в буфер обмена**. "
                     f"Подключите кошелек к сайту Aptos Explorer. В открывшемся окне в поля **T0** и **T1** "
                     f"вставьте скопированный контракт. Далее **RUN**, подпишите транзакцию — и монеты $MEE в кошельке!")
        tk.Label(self.tips_frame, text=tip2_text, font=("Arial", 9), justify=tk.LEFT, wraplength=900, fg="#333333", bg="#FFFFFF").pack(pady=(2, 5), anchor='w')


        # Инициализация при старте
        self.initialize_view()

    def harvest_and_copy(self):
        """Копирует контракт и открывает ссылку Harvest."""
        
        # 1. Копируем контракт MEE в буфер обмена
        self.copy_to_clipboard(MEE_COIN_T0_T1, self.copy_notification_label)
        
        # 2. Небольшое уведомление о копировании
        self.copy_notification_label.config(text="✅ Контракт скопирован!", fg="green")
        self.master.after(2000, lambda: self.copy_notification_label.config(text=""))
        
        # 3. Открываем Harvest URL
        open_url(HARVEST_BASE_URL)


    # --- МЕТОД ДЛЯ КОПИРОВАНИЯ И ОПОВЕЩЕНИЯ ---
    def copy_to_clipboard(self, value, notification_label):
        """Копирует значение в буфер обмена."""
        self.master.clipboard_clear()
        self.master.clipboard_append(value)
        self.master.update() 
        
    def center_window(self, width, height):
        """Центрирует окно на экране."""
        screen_width = self.master.winfo_screenwidth()
        screen_height = self.master.winfo_screenheight()
        
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        
        self.master.geometry(f'{width}x{height}+{x}+{y}')
        
    def initialize_view(self):
        """Устанавливает начальный вид в зависимости от наличия кошелька."""
        is_example = self.current_wallet == DEFAULT_EXAMPLE_ADDRESS

        if self.is_running:
            wallet_display = f"{self.current_wallet[:6]}...{self.current_wallet[-4:]}"
            self.wallet_label.config(text=wallet_display, fg="purple")
            
            if is_example:
                self.status_message.config(
                    text="⚠️ Сейчас используется **пример** адреса. Нажмите 'Изменить', чтобы ввести свой.", 
                    fg="darkorange"
                )
            else:
                self.status_message.config(text="")
                
            self.run_update_in_thread() 
            self.run_periodic_tasks()
        else:
            self.wallet_label.config(text="Не установлен", fg="red")
            self.status_message.config(
                text="⚠️ Критическая ошибка: Не удалось даже загрузить адрес по умолчанию.", 
                fg="red"
            )

    def open_edit_wallet_dialog(self):
        """Открывает диалог для редактирования адреса кошелька."""
        initial_val = self.current_wallet
        new_address = simpledialog.askstring(
            "Изменить кошелек", 
            "Введите новый адрес Aptos кошелька (66 символов, 0x...):", 
            initialvalue=initial_val,
            parent=self.master
        )
        
        if new_address:
            new_address = new_address.strip()
            if len(new_address) == 66 and new_address.startswith("0x"):
                try:
                    save_wallet_address(new_address)
                    
                    self.current_wallet = new_address
                    self.is_running = True
                    self.wallet_label.config(text=f"{self.current_wallet[:6]}...{self.current_wallet[-4:]}", fg="purple")
                    self.status_message.config(text="")
                    
                    global ACCOUNT_ADDRESS, STAKE_API_URL, POOL_API_URL
                    ACCOUNT_ADDRESS = self.current_wallet
                    STAKE_API_URL, POOL_API_URL = generate_api_urls(ACCOUNT_ADDRESS)
                    
                    # Перезапуск логики обновления
                    if self.simulation_job:
                        self.master.after_cancel(self.simulation_job)
                    self.run_update_in_thread() 
                    self.run_periodic_tasks() 
                        
                    messagebox.showinfo("Успех", "Адрес кошелька обновлен и сохранен. Запускается обновление данных.")
                except Exception as e:
                    messagebox.showerror("Ошибка сохранения", f"Не удалось сохранить адрес: {e}")
            else:
                messagebox.showerror("Ошибка", "Неверный формат адреса кошелька (должен быть 66 символов и начинаться с 0x).")

    def run_update_in_thread(self):
        """Запускает обновление данных в отдельном потоке (API call)."""
        if not self.is_running:
            return
            
        self.countdown_val = UPDATE_INTERVAL_SECONDS
        
        thread = threading.Thread(target=self.fetch_and_update, daemon=True) 
        thread.start()

    def fetch_and_update(self):
        """Получает данные и вызывает обновление GUI."""
        if not self.is_running:
            return

        global ACCOUNT_ADDRESS, STAKE_API_URL, POOL_API_URL
        STAKE_API_URL, POOL_API_URL = generate_api_urls(self.current_wallet)

        mee_balance, mee_total_reward_raw, mee_rate = get_all_rewards()
        results = (mee_balance, mee_total_reward_raw, mee_rate) 
        
        self.master.after(0, lambda: self.update_labels(results))

    def update_labels(self, results):
        """Обновляет метки GUI и устанавливает базовые значения для симуляции."""
        if not self.is_running:
            return
            
        mee_balance, mee_total_reward_raw, mee_rate = results
        
        error_text = "Ошибка! Проверьте кошелек или сеть."

        if mee_balance is None:
            self.mee_balance_value_label.config(text=error_text, fg="red")
            self.mee_reward_value_label.config(text=error_text, fg="red")
            return
            
        # Устанавливаем новые базовые значения
        self.mee_current_reward = mee_total_reward_raw * 100 
        self.mee_rate_per_sec = mee_rate
        
        balance_scaled = mee_balance * 100 
        balance_str = f"{balance_scaled:,.8f} $MEE".replace(",", " ").replace(".", ",")
        
        self.mee_balance_value_label.config(text=balance_str, fg="black")

        self._update_reward_labels()

    def _update_reward_labels(self):
        """Обновляет только метки награды (симуляция)."""
        
        mee_reward_str = f"{self.mee_current_reward:,.8f} $MEE".replace(",", " ").replace(".", ",")
        self.mee_reward_value_label.config(text=mee_reward_str, fg="green")


    def run_periodic_tasks(self):
        """Цикл, управляющий симуляцией роста награды и невидимым 60-секундным таймером."""
        if not self.is_running:
            return
            
        self.mee_current_reward += self.mee_rate_per_sec
        self._update_reward_labels() 

        self.countdown_val -= 1
        
        if self.countdown_val >= 0:
            self.simulation_job = self.master.after(1000, self.run_periodic_tasks)
        else:
            self.run_update_in_thread() 
            self.simulation_job = self.master.after(1000, self.run_periodic_tasks)

# --- Запуск ---
if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = MeeiroApp(root)
        
        def on_closing():
            if app.simulation_job:
                root.after_cancel(app.simulation_job)
            root.destroy()
            
        root.protocol("WM_DELETE_WINDOW", on_closing)
        
        root.mainloop()
    except Exception as e:
        messagebox.showerror("Ошибка", f"Произошла критическая ошибка: {e}")
