import streamlit as st
import numpy as np
import pandas as pd
from io import BytesIO
from datetime import timedelta
from math import ceil
from datetime import datetime

# Функция для распределения товаров по вагонеткам
def distribute_to_trolleys(df):
    # Добавление столбца для количества необходимых листов
    df['Необходимо листов'] = np.ceil(df['Количество изделий план'] / df['Количество на листе'])
    
    # Сортировка по типу теста и температуре для последовательного распределения
    sorted_df = df.sort_values(by=['Тип теста', 'Температура Печи'])
    
    # Создание DataFrame для вагонеток
    trolley_df = pd.DataFrame()
    
    # Счетчик вагонеток
    trolley_counter = 1
    
    # Проходим по каждой группе товаров с одинаковым типом теста и температурой печи
    for (test_type, temp), group in sorted_df.groupby(['Тип теста', 'Температура Печи']):
        # Сброс счетчика листов в текущей вагонетке
        current_trolley_sheets = 0
        # Сброс индекса для правильного доступа к строкам группы
        group = group.reset_index(drop=True)

        # Проходим по каждой строке в группе
        for idx, row in group.iterrows():
            sheets_needed = row['Необходимо листов']
            # Распределение товара по вагонеткам
            while sheets_needed > 0:
                # Определяем, сколько листов можем разместить в текущей вагонетке
                available_sheets = min(row['Количество листов в вагонетке'] - current_trolley_sheets, sheets_needed)
                
                # Если нет места в текущей вагонетке, переходим к следующей
                if available_sheets <= 0:
                    trolley_counter += 1
                    current_trolley_sheets = 0
                    continue
                
                # Размещаем листы в вагонетке
                trolley_id = f'Вагонетка {trolley_counter}'
                trolley_df.at[trolley_id, row['Наименование товара']] = available_sheets + trolley_df.get((trolley_id, row['Наименование товара']), 0)
                
                # Уменьшаем количество оставшихся листов
                sheets_needed -= available_sheets
                current_trolley_sheets += available_sheets

                # Если текущая вагонетка заполнена, переходим к следующей
                if current_trolley_sheets >= row['Количество листов в вагонетке']:
                    trolley_counter += 1
                    current_trolley_sheets = 0

    # Заполнение нулями отсутствующих значений
    trolley_df = trolley_df.fillna(0)

    return trolley_df
def distribute_to_trolleys_sorted(df):
    # Конвертация 'кусок' в NaN или другое специфическое число, если необходимо
    df['Размер зуваляшки'] = pd.to_numeric(df['Размер зуваляшки'], errors='coerce').fillna(999)
    df['Тип теста'] = pd.Categorical(df['Тип теста'], categories=['сладкое', 'соленое'], ordered=True)
    df = df.sort_values(by=['Тип теста', 'Размер зуваляшки', 'Количество листов в вагонетке'], ascending=[True, False, False])
    df.reset_index(drop=True, inplace=True)
    return distribute_to_trolleys(df)



# Функция для распределения вагонеток по печам
def schedule_oven_operations(start_shift, end_shift, num_ovens, change_trolley_time, change_temp_time, trolley_df):
    # Преобразование времени начала и окончания смены в объекты datetime
    start_shift = datetime.strptime(start_shift, '%H:%M')
    end_shift = datetime.strptime(end_shift, '%H:%M')
    
    # Инициализация расписания для каждой печи
    ovens_schedule = {f'Печь {i+1}': [] for i in range(num_ovens)}
    
    # Время последней операции в каждой печи
    last_operation_time = {f'Печь {i+1}': start_shift for i in range(num_ovens)}
    
    # Текущий температурный режим каждой печи
    current_temp = {f'Печь {i+1}': None for i in range(num_ovens)}
    
    # Обход всех вагонеток в df
    for _, trolley in trolley_df.iterrows():
        # Выбор печи с ближайшим доступным временем
        next_oven = min(last_operation_time, key=last_operation_time.get)
        
        # Время начала выпекания в выбранной печи
        start_baking_time = last_operation_time[next_oven]
        
        # Проверка необходимости смены температурного режима
        if current_temp[next_oven] != trolley['Температура Печи']:
            start_baking_time += timedelta(minutes=change_temp_time)
            current_temp[next_oven] = trolley['Температура Печи']
        
        # Добавление времени выпекания и времени на смену вагонетки
        end_baking_time = start_baking_time + timedelta(minutes=trolley['Время'] + change_trolley_time)
        
        # Проверка на окончание смены
        if end_baking_time > end_shift:
            continue  # Если время выпекания выходит за пределы смены, пропустим эту вагонетку
        
        # Расчет длительности выпекания
        duration = (end_baking_time - start_baking_time).seconds // 60  # в минутах
        
        # Состав вагонетки
        trolley_composition = ', '.join([
            f"{product}: {int(trolley[product])} листов ({int(trolley[product]) * df.loc[df['Наименование товара'] == product, 'Количество на листе'].iloc[0]} штук)"
            for product in df['Наименование товара'].unique() if trolley.get(product, 0) > 0
        ])
        
        # Добавление операции выпекания в расписание печи
        ovens_schedule[next_oven].append({
            'Начало': start_baking_time.time(),
            'Конец': end_baking_time.time(),
            'Длительность': duration,
            'Состав вагонетки': trolley_composition,
            'Вагонетка': trolley.name,
            'Температура Печи': trolley['Температура Печи']
        })
        
        # Обновление времени последней операции в печи
        last_operation_time[next_oven] = end_baking_time


def to_df_from_list(dicti):
    schedule_df = pd.DataFrame(dicti)
    # Убедитесь, что 'Начало' и 'Конец' являются правильными временными метками, прежде чем преобразовывать их
    if all(isinstance(x, (int, float)) for x in schedule_df['Начало']):
        schedule_df['Начало'] = pd.to_datetime(schedule_df['Начало'], unit='ns')
        schedule_df['Конец'] = pd.to_datetime(schedule_df['Конец'], unit='ns')
    return schedule_df

def to_excel():
    output = BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    with writer as w:
        for i in pd.DataFrame(ovens_schedule).columns:
            a = to_df_from_list(ovens_schedule[i])
            a.to_excel(writer, sheet_name=i, index=False)
    writer._save()
    return output.getvalue()


st.markdown('''<h3>Файл с данными</h3>''', unsafe_allow_html=True)
df = st.file_uploader("Выберите XLSX файл с данными", accept_multiple_files=False)
if df: 
  df = pd.read_excel(df)
  st.dataframe(df)
  st.dataframe(distribute_to_trolleys_sorted(df))
  ovens_schedule = schedule_oven_operations('13:00', '21:00', 3, 2, 5, df)
  st.dataframe(ovens_schedule)
 
df_xlsx = to_excel()
st.download_button(label='📥 Скачать план в Excel', data=df_xlsx, file_name='Backing_Plan.xlsx')
    
