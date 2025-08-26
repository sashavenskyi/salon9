# -*- coding: utf-8 -*-
"""
Created on Tue Aug 26 16:56:26 2025

@author: olve
"""

import asyncio
from telethon import TelegramClient
import re
from datetime import datetime
import pandas as pd
import os
import json

# --- Налаштування Telegram API ---
API_ID = 28827902
API_HASH = '570a58b3196f392d2c754ff123c9929f'
CHANNEL_ID = -4914800011

# --- Функції для парсингу даних ---
def parse_daily_report(report_text):
    """
    Парсить щоденний звіт з новим, складнішим форматом.
    """
    date_match = re.search(r'Звіт\s+(\d{2}\.\d{2})', report_text)
    if not date_match:
        return None, None
    
    try:
        report_date_str = date_match.group(1) + '.' + str(datetime.now().year)
        report_date = datetime.strptime(report_date_str, '%d.%m.%Y').date()
    except ValueError:
        return None, None

    lines = report_text.strip().split('\n')
    data = []
    summary_data = {}
    
    current_section = "services"
    service_entry = {}
    
    for line in lines:
        line = line.strip()
        if not line:
            continue

        if "Продаж сертифікатів:" in line:
            current_section = "certificates"
            if service_entry:
                data.append(service_entry)
            service_entry = {}
            continue
        if "Витрати:" in line:
            current_section = "expenses"
            if service_entry:
                data.append(service_entry)
            service_entry = {}
            continue
        if "Підсумки дня:" in line:
            current_section = "summary"
            if service_entry:
                data.append(service_entry)
            service_entry = {}
            continue
        if "Продаж косметики:" in line:
            current_section = "cosmetics"
            if service_entry:
                data.append(service_entry)
            service_entry = {}
            continue
        if "На рахунок :" in line:
            current_section = "on_account"
            if service_entry:
                data.append(service_entry)
            service_entry = {}
            continue

        # Уточнена логіка для ідентифікації підсумків дня
        summary_match = re.search(r'(.+):\s*(-?\s*\d+)\s*грн', line)
        if summary_match and (summary_match.group(1).strip() in ["Залишок який був", "Карта", "Готівка", "Всього за день", "Залишок в сейфі"]):
            key = summary_match.group(1).strip()
            value = int(summary_match.group(2).replace(' ', ''))
            summary_data[key] = value
            continue

        if current_section == "services":
            time_match = re.match(r'(\d{1,2}:\d{2})\s(.+)', line)
            if time_match:
                if service_entry:
                    data.append(service_entry)
                service_entry = {
                    'Date': report_date,
                    'Section': 'Service',
                    'Client': time_match.group(2).strip(),
                    'Master': None,
                    'Service': [],
                    'Revenue': None,
                    'PaymentMethod': None
                }
                continue
            
            master_match = re.search(r'\((\w+)\)$', line)
            if master_match and service_entry:
                service_entry['Master'] = master_match.group(1).strip()
                if service_entry['Revenue'] is None:
                    service_entry['Revenue'] = 0
                data.append(service_entry)
                service_entry = {}
                continue
            
            revenue_match = re.search(r'(-?\s*\d+)\s*грн', line)
            if revenue_match and service_entry:
                revenue_value = int(revenue_match.group(1).replace(' ', ''))
                service_entry['Revenue'] = abs(revenue_value)
                continue
            
            payment_match = re.search(r'\((Готівка|Карта)\)', line)
            if payment_match and service_entry:
                service_entry['PaymentMethod'] = payment_match.group(1).strip()
                continue
            
            if service_entry and not master_match and not revenue_match and not payment_match:
                if 'Service' in service_entry:
                    service_entry['Service'].append(line)
                else:
                    service_entry['Service'] = [line]

        if current_section == "certificates":
            revenue_match = re.search(r'(-?\s*\d+)\s*грн', line)
            payment_match = re.search(r'\((\w+)\)', line)
            if revenue_match and payment_match:
                revenue_value = int(revenue_match.group(1).replace(' ', ''))
                data.append({
                    'Date': report_date,
                    'Section': 'Certificate Sale',
                    'Client': line.split('-')[0].strip(),
                    'Master': None,
                    'Service': line.split('-')[0].strip(),
                    'Revenue': abs(revenue_value),
                    'PaymentMethod': payment_match.group(1).strip()
                })
        
        if current_section == "cosmetics":
            revenue_match = re.search(r'(-?\s*\d+)\s*грн', line)
            payment_match = re.search(r'\((\w+)\)', line)
            if revenue_match and payment_match:
                 data.append({
                    'Date': report_date,
                    'Section': 'Cosmetic Sale',
                    'Client': None,
                    'Master': None,
                    'Service': line.split('-')[0].strip(),
                    'Revenue': abs(int(revenue_match.group(1).replace(' ', ''))),
                    'PaymentMethod': payment_match.group(1).strip()
                })
        
        if current_section == "expenses":
            revenue_match = re.search(r'(-?\s*\d+)\s*грн', line)
            if revenue_match:
                data.append({
                    'Date': report_date,
                    'Section': 'Expenses',
                    'Client': None,
                    'Master': None,
                    'Service': line.split('-')[0].strip(),
                    'Revenue': int(revenue_match.group(1).replace(' ', '')),
                    'PaymentMethod': None
                })
        
        if current_section == "on_account":
            revenue_match = re.search(r'(-?\s*\d+)\s*грн', line)
            if revenue_match:
                revenue_value = int(revenue_match.group(1).replace(' ', ''))
                data.append({
                    'Date': report_date,
                    'Section': 'On Account',
                    'Client': line.split(' -')[0].strip(),
                    'Master': None,
                    'Service': line,
                    'Revenue': abs(revenue_value),
                    'PaymentMethod': None
                })

    df = pd.DataFrame(data)
    if 'Service' in df:
        df['Service'] = df['Service'].apply(lambda x: ' / '.join(x) if isinstance(x, list) else x)
    
    return df, summary_data

# --- Основна асинхронна функція для збору даних ---
async def main():
    print("Запускаємо збір даних з Telegram...")
    
    client_name = 'salon_session'
    client = TelegramClient(client_name, API_ID, API_HASH)

    if os.path.exists(f'{client_name}.session'):
        print("Використовуємо збережену сесію.")
    else:
        print("Сесія не знайдена. Потрібна авторизація. Будь ласка, введіть ваш номер телефону.")

    await client.start()
    
    try:
        if not await client.is_user_authorized():
            print("Авторизація не вдалася. Будь ласка, запустіть скрипт знову.")
            return

        print("\nПідключення успішне! Збираємо звіти...")
        reports_found = 0
        
        # Видаляємо старий файл
        if os.path.exists('all_reports.csv'):
            os.remove('all_reports.csv')
            print("Видалено старий файл 'all_reports.csv'.")
            
        async for message in client.iter_messages(CHANNEL_ID):
            if message.text and "Звіт" in message.text and re.search(r'\d{2}\.\d{2}', message.text):
                try:
                    daily_df, daily_summary = parse_daily_report(message.text)
                    if daily_df is not None and not daily_df.empty:
                        with open('all_reports.csv', 'a', encoding='utf-8-sig') as f:
                            daily_df.to_csv(f, header=f.tell()==0, index=False)
                        
                        # Додаємо підсумкові дані в окремі рядки
                        if daily_summary:
                            summary_records = []
                            for key, value in daily_summary.items():
                                summary_records.append({
                                    'Date': daily_df['Date'].iloc[0],
                                    'Section': 'Summary',
                                    'Client': None,
                                    'Master': None,
                                    'Service': key,
                                    'Revenue': value,
                                    'PaymentMethod': None
                                })
                            
                            summary_df = pd.DataFrame(summary_records)
                            with open('all_reports.csv', 'a', encoding='utf-8-sig') as f:
                                summary_df.to_csv(f, header=False, index=False)
                        
                        reports_found += 1
                except Exception as e:
                    print(f"Помилка при обробці звіту від {message.date}: {e}")
        
        print(f"\n✅ Завершено. Знайдено та збережено {reports_found} звітів у файл 'all_reports.csv'.")
    
    except Exception as e:
        print(f"❌ Критична помилка: {e}")
    finally:
        await client.disconnect()
        
if __name__ == '__main__':
    asyncio.run(main())