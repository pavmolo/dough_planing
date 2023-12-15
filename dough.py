import streamlit as st
import numpy as np
import pandas as pd
from io import BytesIO
from datetime import timedelta
from math import ceil
from datetime import datetime
from openpyxl.styles import Alignment
from datetime import datetime, timedelta
import re

def distribute_to_trolleys(df):
    df['Необходимо листов'] = np.ceil(df['Количество изделий план'] / df['Количество на листе'])
    sorted_df = df.sort_values(by=['Тип теста', 'Температура Печи', 'Размер зуваляшки, гр'], ascending=[True, True, False])
    
    trolley_info = {}
    trolley_counter = 1
    
    for _, row in sorted_df.iterrows():
        sheets_needed = row['Необходимо листов']
        
        while sheets_needed > 0:
            trolley_id = f'Вагонетка {trolley_counter}'
            if trolley_id not in trolley_info:
                trolley_info[trolley_id] = {
                    'Температура Печи': row['Температура Печи'],
                    'Время': row['Время'],
                    'Продукция': [],
                    'Листов в Вагонетке': 0
                }
            
            if (trolley_info[trolley_id]['Температура Печи'] != row['Температура Печи'] or
                trolley_info[trolley_id]['Листов в Вагонетке'] >= row['Количество листов в вагонетке']):
                trolley_counter += 1
                continue

            available_sheets = min(row['Количество листов в вагонетке'] - trolley_info[trolley_id]['Листов в Вагонетке'], sheets_needed)
            trolley_info[trolley_id]['Листов в Вагонетке'] += available_sheets

            trolley_info[trolley_id]['Продукция'].append({
                'Наименование товара': row['Наименование товара'],
                'Количество листов': available_sheets,
                'Количество на листе': row['Количество на листе']
            })

            sheets_needed -= available_sheets
    
    trolley_df_list = [dict(v, Вагонетка=k) for k, v in trolley_info.items()]
    return pd.DataFrame(trolley_df_list), trolley_info


def distribute_to_trolleys_sorted(df):
    # Конвертация 'кусок' в NaN или другое специфическое число, если необходимо
    df['Размер зуваляшки, гр'] = pd.to_numeric(df['Размер зуваляшки, гр'], errors='coerce').fillna(999)
    df['Тип теста'] = pd.Categorical(df['Тип теста'], categories=['сладкое', 'соленое'], ordered=True)
    df = df.sort_values(by=['Тип теста', 'Размер зуваляшки, гр', 'Количество листов в вагонетке'], ascending=[True, False, False])
    df.reset_index(drop=True, inplace=True)
    return distribute_to_trolleys(df)



# Обновленная функция schedule_oven_operations с добавлением длительности и состава вагонетки
def schedule_oven_operations(start_shift, end_shift, num_ovens, change_trolley_time, change_temp_time, trolley_df, trolley_info):
    start_shift = datetime.strptime(start_shift, '%H:%M')
    end_shift = datetime.strptime(end_shift, '%H:%M')
    ovens_schedule = {f'Печь {i+1}': [] for i in range(num_ovens)}
    last_operation_time = {f'Печь {i+1}': start_shift for i in range(num_ovens)}
    current_temp = {f'Печь {i+1}': None for i in range(num_ovens)}
    
    trolley_composition = pd.DataFrame(columns=['Вагонетка', 'Состав'])
    
    for index, trolley in trolley_df.iterrows():
        next_oven = min(last_operation_time, key=last_operation_time.get)
        start_baking_time = last_operation_time[next_oven]
        
        if current_temp[next_oven] != trolley['Температура Печи']:
            start_baking_time += timedelta(minutes=change_temp_time)
            current_temp[next_oven] = trolley['Температура Печи']
        
        end_baking_time = start_baking_time + timedelta(minutes=trolley['Время'] + change_trolley_time)
        
        if end_baking_time <= end_shift:
            composition_list = [
                f"{prod_info['Наименование товара']}: {prod_info['Количество листов']} листов "
                f"({int(prod_info['Количество листов'] * prod_info['Количество на листе'])} штук)"
                for prod_info in trolley_info[trolley['Вагонетка']]['Продукция']
            ]
            composition = "\n".join(composition_list)
            total_sheets = trolley_info[trolley['Вагонетка']]['Листов в Вагонетке']  # Общее количество листов
            
            new_row = pd.DataFrame({
                'Вагонетка': [trolley['Вагонетка']],
                'Состав': [composition],
                'Листов': [total_sheets]  # Добавляем информацию о листах
            })
            
            trolley_composition = pd.concat([trolley_composition, new_row], ignore_index=True)

            ovens_schedule[next_oven].append({
                'Начало': start_baking_time.time().strftime('%H:%M'),
                'Конец': end_baking_time.time().strftime('%H:%M'),
                'Длительность': trolley['Время'],
                'Вагонетка': trolley['Вагонетка'],
                'Температура Печи': trolley['Температура Печи'],
                'Состав': composition
            })
            
            last_operation_time[next_oven] = end_baking_time
    
    return ovens_schedule, trolley_composition




# Функция для преобразования графика печей в DataFrame
def to_df_from_schedule(ovens_schedule):
    # Преобразование данных расписания в DataFrame
    oven_dfs = []
    for oven, schedule in ovens_schedule.items():
        oven_df = pd.DataFrame(schedule)
        oven_df.insert(0, 'Печь', oven)  # Добавление столбца с названием печи
        oven_dfs.append(oven_df)
    full_schedule_df = pd.concat(oven_dfs, ignore_index=True)
    return full_schedule_df

# Функция для сохранения DataFrame в Excel
def to_excel(oven_schedule_df, trolley_composition_df, df_formovka, zuvalashka_df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        oven_schedule_df.to_excel(writer, sheet_name='Oven Schedule', index=False)
        trolley_composition_df.to_excel(writer, sheet_name='Trolley Composition', index=False)
        df_formovka.to_excel(writer, sheet_name='Form Plan', index=True)
        zuvalashka_df.to_excel(writer, sheet_name='Form Plan', index=True)
        
        # Получаем активный объект workbook и sheet
        workbook  = writer.book
        worksheet = writer.sheets['Trolley Composition']
        
        # Применяем перенос текста ко всем ячейкам
        for row in worksheet.iter_rows():
            for cell in row:
                cell.alignment = Alignment(wrapText=True)

    return output.getvalue()


st.markdown('''<h3>Файл с данными</h3>''', unsafe_allow_html=True)
uploaded_file = st.file_uploader("Выберите XLSX файл с данными", accept_multiple_files=False)

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    sorted_trolleys_df, trolley_info = distribute_to_trolleys_sorted(df)
    ovens_schedule, trolley_composition = schedule_oven_operations('13:00', '21:00', 3, 2, 5, sorted_trolleys_df, trolley_info)

    # Преобразование ovens_schedule в DataFrame
    oven_schedule_list = []
    for oven, schedule_list in ovens_schedule.items():
        for schedule in schedule_list:
            schedule['Печь'] = oven
            oven_schedule_list.append(schedule)
    oven_schedule_df = pd.DataFrame(oven_schedule_list)





    # Предположим, что df - это ваш исходный датафрейм
    df_tor = pd.DataFrame(distribute_to_trolleys(df)[1]).T
    
    # Создаем новый пустой датафрейм
    new_rows = []
    
    # Проходим по всем строкам исходного датафрейма
    for index, row in df_tor.iterrows():
        # Извлекаем данные из столбца 'Продукция'
        products = row['Продукция']
        
        # Для каждого элемента в 'Продукция' создаем новую строку
        for product in products:
            new_row = row.copy()
            new_row['Наименование товара'] = product['Наименование товара']
            new_row['Количество листов'] = product['Количество листов']
            new_row['Количество на листе'] = product['Количество на листе']
            
            # Удаляем старую информацию о продукции
            del new_row['Продукция']
    
            new_rows.append(new_row)
    
    # Преобразуем список новых строк в новый датафрейм
    new_df = pd.DataFrame(new_rows)
    
    split_rows = []
    
    # Проходим по каждой строке исходного датафрейма
    for index, row in oven_schedule_df.iterrows():
        # Разделяем содержимое столбца 'Состав' по переносу строки
        compositions = row['Состав'].split('\n')
        
        # Для каждого элемента в списке создаем новую строку с повторением остальных значений
        for comp in compositions:
            new_row = row.copy()
            new_row['Состав'] = comp
            split_rows.append(new_row)
    
    # Преобразуем список разделенных строк в датафрейм
    split_df = pd.DataFrame(split_rows)
    def extract_quantity(string):
        match = re.search(r'\((\d+) штук\)', string)
        if match:
            return int(match.group(1))
        return None
    
    # Применяем функцию к столбцу 'Состав' и создаем новый столбец 'Количество штук'
    split_df['Количество штук'] = split_df['Состав'].apply(extract_quantity)
    def extract_product_name(string):
        return string.split(':')[0].strip()
    
    # Применяем функцию к столбцу 'Состав' и создаем новый столбец 'Наименование товара'
    split_df['Наименование товара'] = split_df['Состав'].apply(extract_product_name)
    
    # Убедимся, что 'Наименование товара' не является индексом в обоих датафреймах
    new_df['Вагонетка'] = new_df.index
    # Выполним слияние, сохраняя индексы из new_df
    result_df = split_df.merge(df, on='Наименование товара', how='left')
    
    # Функция для вычитания минут из времени
    def subtract_minutes(time_str, minutes):
        # Преобразование строки времени в объект datetime
        time_obj = datetime.strptime(time_str, '%H:%M')
        
        # Вычитание минут
        new_time = time_obj - timedelta(minutes=minutes)
    
        # Преобразование обратно в строку
        return new_time.strftime('%H:%M')
    
    df_vag = pd.DataFrame(index=result_df['Вагонетка'])
    df_vag['Наименование товара'] = result_df['Наименование товара'].values
    df_vag['ШТ'] = result_df['Количество штук'].values
    # Добавляем новый столбец 'Время окончания формовки', игнорируя индексы
    
    df_vag['Время окончания формовки'] = result_df.apply(
        lambda row: subtract_minutes(row['Начало'], row['Длит. от конца формовки до печи, мин']),
        axis=1
    ).values
    df_vag['Длит. формовки'] = result_df['Длит. Формовки (на вагонетку), мин'].values
    df_vag['Время начала формовки'] = df_vag.apply(
        lambda row: subtract_minutes(row['Время окончания формовки'], row['Длит. формовки']),
        axis=1
    ).values
    
    df_vag = df_vag[['Наименование товара', 'ШТ', 'Время начала формовки', 'Время окончания формовки']]
    # Преобразование столбца 'Время начала формовки' в формат времени
    df_vag['Время начала формовки'] = pd.to_datetime(df_vag['Время начала формовки'], format='%H:%M')
    
    # Форматирование времени без секунд
    df_vag['Время начала формовки'] = df_vag['Время начала формовки'].dt.strftime('%H:%M')
    
    # Сортировка DataFrame по столбцу 'Время начала формовки'
    df_sorted = df_vag.sort_values(by='Время начала формовки')

    zuvalashka_start = df_sorted.merge(df, on='Наименование товара', how='left')
    zuvalashka_start['Время оконч. изг. зуваляшек'] = zuvalashka_start.apply(
        lambda row: subtract_minutes(row['Время начала формовки'], row['Длит. Отстоя зуваляжки, мин']),
        axis=1
    )
    zuvalashka_start['Время начала изг. зуваляшек'] = zuvalashka_start.apply(
        lambda row: subtract_minutes(row['Время оконч. изг. зуваляшек'], row['Длит. формовки зуваляжки, мин']),
        axis=1
    )
    zuvalashka_start 
    zuvalashka_df = pd.pivot_table(zuvalashka_start, values='ШТ', index=['Время начала изг. зуваляшек', 'Время оконч. изг. зуваляшек', 'Размер зуваляшки, гр'], aggfunc='sum')



    
    # Теперь вызываем функцию to_excel с необходимыми аргументами
    df_xlsx = to_excel(oven_schedule_df, trolley_composition, df_sorted, zuvalashka_df)
    st.download_button(label='📥 Скачать план в Excel', data=df_xlsx, file_name='Backing_Plan.xlsx')

    
