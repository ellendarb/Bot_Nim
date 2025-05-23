# Telegram NIM Bot

Телеграм-бот с реализацией математической игры **"Ним"**

Бот поддерживает два режима игры:  
- **Стандартный**, с фиксированным количеством кучек и числом камней  
- **Кастомный**, где пользователь сам задаёт количество кучек и начальное число камней в каждой из них  

Играть можно как **против бота**, так и **с другим пользователем** Telegram — реализована полноценная игровая логика с синхронизацией и обработкой очередности ходов.

Сложность игры регулируется уровнями: **легко**, **средне**, **сложно**.  
В зависимости от выбранного уровня бот играет с разной точностью — за счёт настроенных вероятностных алгоритмов, а не просто случайных ходов. Например, на лёгком уровне он может допустить просчёт, а на сложном — действует практически безошибочно, используя математическую стратегию выигрыша.

---
## ⚙️ Требования

- Python 3.8+
- Библиотеки:
  - `pyTelegramBotAPI`
  - `python-dotenv`

---

## 🚀 Установка и запуск

1. **Клонировать репозиторий и перейти в папку**  
   ```bash
   git clone https://github.com/ellendarb/Bot_Nim.git
   cd Bot_Nim
2. **(Опционально) Создать и активировать виртуальное окружение**
   ```bash
   python3 -m venv venv
   source venv/bin/activate    # macOS/Linux
   venv\Scripts\activate       # Windows
4. **Установить зависимости**
   ```bash
   pip install -r requirements.txt
5. **Токен**
  Оставить имеющийся или отредактировать в коде API_KEY, подставив вместо него свой токен
5. **Запуск**
   ```bash
   python main.py
