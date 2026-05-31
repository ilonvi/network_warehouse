import streamlit as st
import pandas as pd
from db_config import get_db_connection

st.set_page_config(page_title="Network Warehouse OS", layout="centered")


st.title("ОБЛІК МЕРЕЖЕВОГО ОБЛАДНАННЯ")
st.caption("Програмний комплекс моніторингу залишків та аудиту операцій центру мережевого обладнання")


menu = ["Аналітична панель", "Номенклатура", "Проведення операцій", "Журнал аудиту"]
choice = st.segmented_control("Навігація системи:", menu, default="Аналітична панель", label_visibility="collapsed")
st.divider()

conn = get_db_connection()

if conn:
    
    with conn.cursor(dictionary=True) as cursor, conn:
        
        cursor.execute("SELECT p.*, c.name AS category FROM products p LEFT JOIN categories c ON p.category_id = c.id")
        df_products = pd.DataFrame(cursor.fetchall()) if cursor.rowcount else pd.DataFrame()

        
        
    
        if choice == "Аналітична панель":
            if not df_products.empty:
                col1, col2, col3, col4 = st.columns([1.5, 2, 2, 3.5])
                col1.metric("Моделей", len(df_products))
                col2.metric("Всього одиниць", int(df_products['stock_quantity'].sum()))
                col3.metric("Дефіцит", len(df_products[df_products['stock_quantity'] < 5]), delta_color="inverse")
                col4.metric("Оцінка складу", f"{(df_products['price'] * df_products['stock_quantity']).sum():,.0f} ₴")

                st.write("")
                
                c1, c2 = st.columns([3, 2])
                with c1:
                    st.subheader("Аналітика брендів")
                    chart_data = df_products.groupby('brand')['stock_quantity'].sum().reset_index()
                    st.bar_chart(data=chart_data, x='brand', y='stock_quantity', color="#4c0000ff", use_container_width=True)
                with c2:
                    st.subheader("Структура категорій")
                    cat_data = df_products.groupby('category').size().reset_index(name='Моделей')
                    st.dataframe(cat_data, hide_index=True, use_container_width=True)

                low_stock = df_products[df_products['stock_quantity'] < 5]
                if not low_stock.empty:
                    st.error("Позиції, що потребують термінового поповнення:")
                    st.dataframe(low_stock[['brand', 'model', 'stock_quantity']], hide_index=True, use_container_width=True)
            else:
                st.info("База даних порожня. Додайте номенклатуру.")

        
        elif choice == "Номенклатура":
            tab1, tab2, tab3 = st.tabs(["Реєстр товарів", "Новий товар", "Нова категорія"])
            
            with tab1:
                if not df_products.empty:
                    search = st.text_input("Швидкий пошук:", placeholder="Введіть бренд або модель для фільтрації...")
                    display_df = df_products.copy()
                    if search:
                        display_df = display_df[display_df['model'].str.contains(search, case=False) | display_df['brand'].str.contains(search, case=False)]
                    
                   
                    st.data_editor(
                        display_df[['id', 'brand', 'model', 'category', 'price', 'stock_quantity', 'specifications']], 
                        column_config={
                            "price": st.column_config.NumberColumn("Ціна", format="%.2f ₴"),
                            "stock_quantity": st.column_config.NumberColumn("Залишок (шт)"),
                            "id": "ID", "brand": "Бренд", "model": "Модель", "category": "Категорія", "specifications": "Специфікація"
                        },
                        use_container_width=True, hide_index=True, disabled=True
                    )
                else:
                    st.info("Реєстр порожній.")

            with tab2:
                cursor.execute("SELECT * FROM categories")
                categories = cursor.fetchall()
                if not categories:
                    st.error("Спочатку створіть хоча б одну категорію!")
                else:
                    cat_options = {c['name']: c['id'] for c in categories}
                    with st.form("add_product_form", clear_on_submit=True):
                        c_left, c_right = st.columns(2)
                        brand = c_left.text_input("Виробник")
                        model = c_left.text_input("Модель")
                        category_id = cat_options[c_left.selectbox("Категорія обладнання", list(cat_options.keys()))]
                        price = c_right.number_input("Вартість (грн)", min_value=0.0, format="%.2f")
                        initial_stock = c_right.number_input("Початковий залишок (шт)", min_value=0, step=1)
                        specs = st.text_area("Технічні характеристики")
                        
                        if st.form_submit_button("Зберегти позицію") and brand and model:
                            cursor.execute("INSERT INTO products (category_id, model, brand, price, stock_quantity, specifications) VALUES (%s, %s, %s, %s, 0, %s)", (category_id, model, brand, price, specs))
                            if initial_stock > 0:
                                cursor.execute("INSERT INTO operation_logs (product_id, operation_type, quantity, comment) VALUES (%s, 'INCOMING', %s, 'Первинне введення номенклатури')", (cursor.lastrowid, initial_stock))
                            conn.commit()
                            st.toast("Товар успішно додано")
                            st.rerun()

            with tab3:
                with st.form("add_cat_form", clear_on_submit=True):
                    cat_name = st.text_input("Назва нової категорії")
                    cat_desc = st.text_input("Опис категорії")
                    if st.form_submit_button("Створити категорію") and cat_name:
                        try:
                            cursor.execute("INSERT INTO categories (name, description) VALUES (%s, %s)", (cat_name, cat_desc))
                            conn.commit()
                            st.toast("Категорію зареєстровано")
                            st.rerun()
                        except:
                            st.error("Така категорія вже існує")

        
        elif choice == "Проведення операцій":
            if df_products.empty:
                st.info("Немає доступних товарів")
            else:
                product_options = {f"{r['brand']} {r['model']} [Залишок: {r['stock_quantity']} шт]": r['id'] for _, r in df_products.iterrows()}
                
                with st.form("operation_form", clear_on_submit=True):
                    selected_prod = st.selectbox("Оберіть товар для складу:", list(product_options.keys()))
                    prod_id = product_options[selected_prod]
                    
                    col_op, col_qty = st.columns(2)
                    op_type = col_op.selectbox("Тип операції:", ["Прихід", "Розхід", "Списання нестачі", "Оприбуткування надлишку"])
                    qty = col_qty.number_input("Кількість (шт):", min_value=1, step=1)
                    comment = st.text_input("Коментар до операції:")
                    
                    if st.form_submit_button("Провести операцію"):
                        current_stock = df_products[df_products['id'] == prod_id]['stock_quantity'].values[0]
                        
                        
                        db_op_type = "INCOMING" if "Прихід" in op_type else "OUTGOING" if "Розхід" in op_type else "CORRECTION"
                        final_qty = -qty if "нестачі" in op_type or "Розхід" in op_type else qty

                        if db_op_type == "OUTGOING" and current_stock < qty:
                            st.error("Помилка: Недостатньо товару на складі!")
                        else:
                            cursor.execute("INSERT INTO operation_logs (product_id, operation_type, quantity, comment) VALUES (%s, %s, %s, %s)", (prod_id, db_op_type, final_qty, comment))
                            conn.commit()
                            st.toast("Операцію успішно проведено!")
                            st.rerun()

        
        elif choice == "Журнал аудиту":
            st.subheader("Історія руху матеріальних цінностей")
            cursor.execute("""
                SELECT l.id AS 'ID', CONCAT(p.brand, ' ', p.model) AS 'Товар', 
                       l.operation_type AS 'Операція', l.quantity AS 'Кількість', 
                       l.operation_date AS 'Дата/Час', l.comment AS 'Коментар'
                FROM operation_logs l JOIN products p ON l.product_id = p.id ORDER BY l.operation_date DESC
            """)
            logs = cursor.fetchall()
            if logs:
                st.dataframe(pd.DataFrame(logs), use_container_width=True, hide_index=True)
            else:
                st.info("Журнал операцій порожній.")