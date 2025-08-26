# -*- coding: utf-8 -*-
"""
Created on Tue Aug 26 16:56:39 2025

@author: olve
"""

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os

# Завантаження даних
@st.cache_data
def load_data(file_path):
    if not os.path.exists(file_path):
        st.error(f"Файл '{file_path}' не знайдено. Будь ласка, запустіть скрипт 'telegram_collector.py' для збору даних.")
        return pd.DataFrame()
    try:
        df = pd.read_csv(file_path, encoding='utf-8-sig')
        # Очищення даних від невідомих символів
        df = df.replace({r'[^\w\s\-\,\.\(\)\/\%\:]': ''}, regex=True)
        # Примусове перетворення Revenue на числовий формат
        df['Revenue'] = pd.to_numeric(df['Revenue'], errors='coerce')
        return df
    except Exception as e:
        st.error(f"Помилка при завантаженні файлу: {e}")
        return pd.DataFrame()

# Завантажуємо дані
df_raw = load_data('all_reports.csv')

if not df_raw.empty:
    df_raw['Date'] = pd.to_datetime(df_raw['Date'])
    
    # Розділяємо дані на транзакції та підсумки
    df_summary = df_raw[df_raw['Section'] == 'Summary'].copy()
    df = df_raw[df_raw['Section'] != 'Summary'].copy()

    st.title("Аналіз звітів з Telegram-каналу")
    st.markdown("---")

    # Відображення загальної виручки
    st.header("Загальна виручка за весь період")
    total_revenue_all_time = 0
    if not df_summary.empty:
        # Розраховуємо загальну виручку шляхом підсумовування 'Всього за день' з усіх звітів
        total_revenue_all_time = df_summary[df_summary['Service'] == 'Всього за день']['Revenue'].sum()
    st.metric("Загальна виручка (за всі дні)", f"{total_revenue_all_time:,.0f} грн")
    st.markdown("---")

    # Відображення підсумків за днями
    if not df_summary.empty:
        st.header("Фінансові підсумки за днями")
        summary_display_df = df_summary.pivot_table(index='Date', columns='Service', values='Revenue').sort_index(ascending=False)
        st.dataframe(summary_display_df.style.format("{:,.0f} грн"))
        st.markdown("---")

    # Фінансовий підсумок останнього дня
    if not df_summary.empty:
        st.header("Останній фінансовий звіт")
        
        # Знаходимо останній звіт за датою
        latest_date = df_summary['Date'].max()
        latest_summary_df = df_summary[df_summary['Date'] == latest_date].set_index('Service')
        
        col1, col2, col3 = st.columns(3)
        
        # Виводимо дані, використовуючи .get() для уникнення помилок
        col1.metric("Залишок, який був", f"{latest_summary_df.loc['Залишок який був', 'Revenue']:.0f} грн" if 'Залишок який був' in latest_summary_df.index else "Дані відсутні")
        col2.metric("Всього за день", f"{latest_summary_df.loc['Всього за день', 'Revenue']:.0f} грн" if 'Всього за день' in latest_summary_df.index else "Дані відсутні")
        col3.metric("Залишок в сейфі", f"{latest_summary_df.loc['Залишок в сейфі', 'Revenue']:.0f} грн" if 'Залишок в сейфі' in latest_summary_df.index else "Дані відсутні")

        st.markdown("---")
    
    # Фільтри
    st.sidebar.header("Фільтри")
    start_date = st.sidebar.date_input("Початкова дата", df['Date'].min())
    end_date = st.sidebar.date_input("Кінцева дата", df['Date'].max())

    filtered_df = df[(df['Date'] >= pd.to_datetime(start_date)) & (df['Date'] <= pd.to_datetime(end_date))]
    
    if filtered_df.empty:
        st.warning("За вибраний період дані відсутні.")
    else:
        st.header("Огляд даних")
        st.dataframe(filtered_df)
        st.markdown("---")
        
        st.header("Дохід за майстрами")
        master_revenue = filtered_df[
            (filtered_df['Section'] != 'Expenses')
        ].groupby('Master')['Revenue'].sum().sort_values(ascending=False)
        
        fig, ax = plt.subplots()
        sns.barplot(x=master_revenue.index, y=master_revenue.values, ax=ax)
        plt.xticks(rotation=45, ha='right')
        plt.ylabel("Дохід (грн)")
        st.pyplot(fig)
        st.markdown("---")
        
        st.header("Дохід за послугами")
        service_revenue = filtered_df[
            filtered_df['Section'] != 'Expenses'
        ].groupby('Service')['Revenue'].sum().sort_values(ascending=False).head(10)
        
        fig, ax = plt.subplots()
        sns.barplot(x=service_revenue.index, y=service_revenue.values, ax=ax)
        plt.xticks(rotation=90, ha='right')
        plt.ylabel("Дохід (грн)")
        st.pyplot(fig)
        st.markdown("---")
        
        st.header("Розподіл типів оплати")
        payment_counts = filtered_df[
            filtered_df['PaymentMethod'].isin(['Готівка', 'Карта'])
        ]['PaymentMethod'].value_counts()
        
        fig, ax = plt.subplots()
        ax.pie(payment_counts, labels=payment_counts.index, autopct='%1.1f%%', startangle=90)
        ax.axis('equal')
        st.pyplot(fig)