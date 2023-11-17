import streamlit as st
import numpy as np
import pandas as pd
from io import BytesIO
from datetime import timedelta
from math import ceil
def distribute_to_trolleys_sorted(df):
    # Преобразование Размер зуваляшки в числовой формат, 'кусок' будет иметь высокое числовое значение для сортировки в конце
    df['Вес зуваляшки'] = df['Размер зуваляшки'].replace('кусок', 999).astype(int)
    
    # Сортировка по типу теста (сладкое, затем соленое), весу зуваляшки (по убыванию) и количеству листов в вагонетке (по убыванию)
    df = df.sort_values(by=['Тип теста', 'Вес зуваляшки', 'Количество листов в вагонетке'], ascending=[True, False, False])

    # Сброс индекса после сортировки
    df.reset_index(drop=True, inplace=True)
    
    # Вызов функции распределения продукции по вагонеткам с уже отсортированным DataFrame
    return distribute_to_trolleys(df)
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

# Теперь переопределим функцию create_full_baking_schedule с учетом наличия df_products_sorted
def create_full_baking_schedule(df, temp_for_oven1, start_time, reset_time=10, basket_interval=3):
    # Инициализация начального времени для каждой печи
    oven1_time = pd.to_datetime(start_time)
    oven2_time = pd.to_datetime(start_time)
    # Последняя температура для определения необходимости перенастройки
    last_temp_oven1 = temp_for_oven1
    last_temp_oven2 = None

    # Инициализация расписания выпекания
    baking_schedule = []

    # Перебор SKU для планирования по печам
    for index, row in df.iterrows():
        oven_time = oven1_time if row['Температура Печи'] == temp_for_oven1 else oven2_time
        oven_name = "Печь 1" if row['Температура Печи'] == temp_for_oven1 else "Печь 2"
        last_temp = last_temp_oven1 if oven_name == "Печь 1" else last_temp_oven2

        # Если температура изменилась, добавляем время на перенастройку
        if last_temp != row['Температура Печи']:
            baking_schedule.append([oven_name, "Перенастройка", "", last_temp, oven_time, "", "", reset_time])
            oven_time += timedelta(minutes=reset_time)

        # Планирование выпекания для каждой вагонетки
        for basket in range(1, row['Кол-во вагонеток'] + 1):
            baking_schedule.append([oven_name, row['Наименование товара'], basket, row['Температура Печи'], oven_time, oven_time - timedelta(hours=1.4), oven_time - timedelta(hours=3.3), row['Время']])
            oven_time += timedelta(minutes=row['Время'] + basket_interval)

        # Обновляем время последней выпекаемой вагонетки и температуру для печи
        if oven_name == "Печь 1":
            oven1_time = oven_time
            last_temp_oven1 = row['Температура Печи']
        else:
            oven2_time = oven_time
            last_temp_oven2 = row['Температура Печи']
        df = pd.DataFrame(baking_schedule, columns=["Печь", "Наименование товара", "Вагонетка", "Температура Печи", "Время начала выпекания", "Время формовки", "Время замеса", "Длительность"])
        # Преобразование строк в datetime объекты, а затем форматирование их как 'HH:MM'
        df['Время начала выпекания'] = pd.to_datetime(df['Время начала выпекания']).dt.strftime('%H:%M')
        df['Время формовки'] = pd.to_datetime(df['Время формовки']).dt.strftime('%H:%M')
        df['Время замеса'] = pd.to_datetime(df['Время замеса']).dt.strftime('%H:%M')

    return df

def to_excel():
    output = BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    with writer as w:
        for i in final_res:
            i.to_excel(writer, sheet_name=i["Печь"].unique()[0], index=False)
    writer._save()
    return output.getvalue()


st.markdown('''<h3>Файл с данными</h3>''', unsafe_allow_html=True)
df = st.file_uploader("Выберите XLSX файл с данными", accept_multiple_files=False)
if df: 
  df = pd.read_excel(df)
  df = distribute_to_trolleys_sorted(df)
  st.dataframe(distribute_to_trolleys(df))
  df_products = df
  # Установка порядка для категориальных данных
  df_products['Тип теста'] = pd.Categorical(df_products['Тип теста'], categories=['сладкое', 'соленое'], ordered=True)
  df_products['Есть сироп'] = pd.Categorical(df_products['Есть сироп'], categories=['да', 'нет'], ordered=True)
    
  # Сортировка по этим категориям сначала, а затем по температуре печи
  df_products_sorted = df_products.sort_values(by=['Тип теста', 'Есть сироп', 'Температура Печи'], ascending=[True, False, False])
  final_res = []
  shift_start = '13:00'
  for i in df_products_sorted["Температура Печи"].unique():
      full_baking_schedule = create_full_baking_schedule(df_products_sorted, i, shift_start)
      full_baking_schedule = full_baking_schedule[full_baking_schedule['Печь'] == "Печь 1"]
      full_baking_schedule["Печь"] = f'Печ режим {i}'
      final_res.append(full_baking_schedule)
 
df_xlsx = to_excel()
st.download_button(label='📥 Скачать план в Excel', data=df_xlsx, file_name='Backing_Plan.xlsx')
    
