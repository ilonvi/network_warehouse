import pandas as pd
import streamlit as st
from db_config import get_db_connection

# Налаштування сторінки
st.set_page_config(page_title="Network Warehouse", layout="wide")



# --- СИСТЕМА АВТОРИЗАЦІЇ ТА РОЛЕЙ ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "user_role" not in st.session_state:
    st.session_state.user_role = None

def login(username, password):
    # Паролі для входу на сайт тепер теж беруться з хмарного сейфа Streamlit Secrets
    if username == "admin" and password == st.secrets["ADMIN_PASSWORD"]:
        st.session_state.authenticated = True
        st.session_state.user_role = "Адміністратор"
        st.rerun()
    elif username == "manager" and password == st.secrets["MANAGER_PASSWORD"]:
        st.session_state.authenticated = True
        st.session_state.user_role = "Менеджер"
        st.rerun()
    else:
        st.error("Неправильний логін або пароль!")

def logout():
    st.session_state.authenticated = False
    st.session_state.user_role = None
    st.rerun()


# --- ВІКНО ВХОДУ ---
if not st.session_state.authenticated:
    st.subheader("Вхід до системи обліку")
    with st.form("login_form", clear_on_submit=False):
        username = st.text_input("Логін")
        password = st.text_input("Пароль", type="password")
        submit = st.form_submit_button("Увійти")
        if submit:
            login(username, password)
    st.stop()


# --- ГОЛОВНИЙ ІНТЕРФЕЙС ---
log_col1, log_col2 = st.columns([8, 2])
with log_col1:
    st.title("ОБЛІК МЕРЕЖЕВОГО ОБЛАДНАННЯ")
    st.caption(f"Авторизовано як: **{st.session_state.user_role}**")
with log_col2:
    st.write("")  # Невеликий відступ для вирівнювання кнопки
    if st.button("Вийти з аккаунту", use_container_width=True):
        logout()


# --- ДИНАМІЧНА НАВІГАЦІЯ ЗАЛЕЖНО ВІД РОЛІ ---
if st.session_state.user_role == "Адміністратор":
    menu = ["Аналітична панель", "Номенклатура", "Проведення операцій", "Журнал аудиту"]
else:
    # Менеджер має обмежені права — не бачить операцій та журналу аудиту
    menu = ["Аналітична панель", "Номенклатура"]

choice = st.segmented_control("Навігація системи:", menu, default="Аналітична панель", label_visibility="collapsed")
st.divider()

conn = get_db_connection()

if conn:
    cursor = conn.cursor()
    
    # Завантаження актуальних даних про товари з бази
    cursor.execute("""
        SELECT p.id, p.brand, p.model, p.price, p.stock_quantity, p.specifications, p.image_url, c.name AS category 
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
    """)
    raw_data = cursor.fetchall()
    
    if raw_data:
        df_products = pd.DataFrame(raw_data)
    else:
        df_products = pd.DataFrame(columns=["id", "brand", "model", "price", "stock_quantity", "specifications", "image_url", "category"])

    # --- 1. АНАЛІТИЧНА ПАНЕЛЬ (Бачать усі) ---
    if choice == "Аналітична панель":
        if not df_products.empty:
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Моделей", len(df_products))
            col2.metric("Всього одиниць", int(df_products["stock_quantity"].sum()))
            col3.metric("Дефіцит", len(df_products[df_products["stock_quantity"] < 5]), delta_color="inverse")
            col4.metric("Оцінка складу", f"{(df_products['price'] * df_products['stock_quantity']).sum():,.0f} ₴")

            st.divider()
            c1, c2 = st.columns([3, 2])
            with c1:
                st.subheader("Аналітика брендів")
                chart_data = df_products.groupby("brand")["stock_quantity"].sum().reset_index()
                st.bar_chart(chart_data, x="brand", y="stock_quantity")
            with c2:
                st.subheader("Категорії")
                cat_data = df_products.groupby("category").size().reset_index(name="Моделей")
                st.dataframe(cat_data, hide_index=True, use_container_width=True)

            low_stock = df_products[df_products["stock_quantity"] < 5]
            if not low_stock.empty:
                st.error("Потребують поповнення:")
                st.dataframe(low_stock[["brand", "model", "stock_quantity"]], hide_index=True, use_container_width=True)
        else:
            st.info("База порожня.")

    # --- 2. НОМЕНКЛАТУРА ---
    elif choice == "Номенклатура":
        # Якщо Адмін — показуємо всі таби. Якщо Менеджер — тільки реєстр (перегляд)
        if st.session_state.user_role == "Адміністратор":
            tabs_list = ["Реєстр", "Новий товар", "Категорії"]
        else:
            tabs_list = ["Реєстр"]
            
        tabs = st.tabs(tabs_list)
        
        # ТАБ: РЕЄСТР (Доступний Адміну та Менеджеру)
        with tabs[0]:
            if not df_products.empty:
                search = st.text_input("Пошук за брендом або моделлю")
                display_df = df_products.copy()
                if search:
                    display_df = display_df[
                        display_df["model"].str.contains(search, case=False, na=False) |
                        display_df["brand"].str.contains(search, case=False, na=False)
                    ]
                
                st.subheader("Картка детального перегляду")
                item_options = {f"{r['brand']} {r['model']}": r for _, r in display_df.iterrows()}
                selected_preview = st.selectbox("Оберіть товар для перегляду:", ["-- Не обрано --"] + list(item_options.keys()))
                
                if selected_preview != "-- Не обрано --":
                    prod_data = item_options[selected_preview]
                    img_col, info_col = st.columns([1, 2])
                    
                    with img_col:
                        if pd.notna(prod_data['image_url']) and str(prod_data['image_url']).strip() != "":
                            st.image(prod_data['image_url'], caption=selected_preview, use_container_width=True)
                        else:
                            st.image("https://i.pinimg.com/originals/28/06/32/280632245663b095081f37cc49a0f17b.gif", caption="Фото відсутнє", use_container_width=True)
                    
                    with info_col:
                        st.markdown(f"**Категорія:** {prod_data['category']}")
                        st.markdown(f"**Ціна:** {prod_data['price']:.2f} ₴")
                        st.markdown(f"**Залишок на складі:** {prod_data['stock_quantity']} шт.")
                        st.markdown(f"**Характеристики:**\n{prod_data['specifications']}")
                
                st.divider()
                st.subheader("Загальний реєстр даних")
                display_df.insert(0, "№ п/п", range(1, len(display_df) + 1))
                cols_to_show = ["№ п/п", "brand", "model", "category", "price", "stock_quantity", "specifications"]
                st.dataframe(display_df[cols_to_show], hide_index=True, use_container_width=True)
            else:
                st.info("Немає товарів")

        # ТАБИ СТВОРЕННЯ (Тільки для Адміністратора)
        if st.session_state.user_role == "Адміністратор":
            with tabs[1]:  # Новий товар
                cursor.execute("SELECT id, name FROM categories")
                categories = cursor.fetchall()
                if not categories:
                    st.warning("Спочатку створіть категорію")
                else:
                    cat_map = {c["name"]: c["id"] for c in categories}
                    with st.form("add_product", clear_on_submit=True):
                        col1, col2 = st.columns(2)
                        brand = col1.text_input("Бренд")
                        model = col1.text_input("Модель")
                        category_name = col1.selectbox("Категорія", list(cat_map.keys()))
                        price = col2.number_input("Ціна", min_value=0.0, format="%.2f")
                        stock = col2.number_input("Початковий залишок", min_value=0, step=1)
                        image_url = st.text_input("Посилання на photo продукту (URL)")
                        specs = st.text_area("Характеристики")

                        if st.form_submit_button("Додати") and brand and model:
                            cursor.execute("""
                                INSERT INTO products (category_id, model, brand, price, stock_quantity, specifications, image_url) 
                                VALUES (%s, %s, %s, %s, 0, %s, %s)
                            """, (cat_map[category_name], model, brand, price, specs, image_url))
                            product_id = cursor.lastrowid
                            
                            if stock > 0:
                                cursor.execute("""
                                    INSERT INTO operation_logs (product_id, operation_type, quantity, comment) 
                                    VALUES (%s, 'INCOMING', %s, 'Initial stock')
                                """, (product_id, stock))
                            
                            conn.commit()
                            st.success("Товар успішно додано!")
                            st.rerun()
                            
            with tabs[2]:  # Категорії
                with st.form("add_category", clear_on_submit=True):
                    name = st.text_input("Назва категорії")
                    desc = st.text_input("Опис категорії")
                    if st.form_submit_button("Створити") and name:
                        try:
                            cursor.execute("INSERT INTO categories (name, description) VALUES (%s, %s)", (name, desc))
                            conn.commit()
                            st.success("Категорію створено")
                            st.rerun()
                        except Exception:
                            st.error("Категорія вже існує")

    # --- 3. ПРОВЕДЕННЯ ОПЕРАЦІЙ (Тільки для Адміністратора) ---
    elif choice == "Проведення операцій" and st.session_state.user_role == "Адміністратор":
        if df_products.empty:
            st.info("Немає товарів для проведення операцій")
        else:
            options = {f"{r['brand']} {r['model']} ({r['stock_quantity']} шт)": r["id"] for _, r in df_products.iterrows()}
            with st.form("operation", clear_on_submit=True):
                selected = st.selectbox("Товар", list(options.keys()))
                prod_id = options[selected]
                col1, col2 = st.columns(2)
                op = col1.selectbox("Операція", ["Прихід", "Розхід", "Списання нестачі", "Оприбуткування надлишку"])
                qty = col2.number_input("Кількість", min_value=1, step=1)
                comment = st.text_input("Коментар")

                if st.form_submit_button("Провести"):
                    current = df_products[df_products["id"] == prod_id]["stock_quantity"].values[0]
                    db_type = "INCOMING" if "Прихід" in op or "надлишку" in op else "OUTGOING" if "Розхід" in op else "CORRECTION"
                    final_qty = -qty if "нестачі" in op else qty

                    if db_type == "OUTGOING" and current < qty:
                        st.error("Недостатньо товару на складі!")
                    else:
                        cursor.execute("""
                            INSERT INTO operation_logs (product_id, operation_type, quantity, comment) 
                            VALUES (%s, %s, %s, %s)
                        """, (prod_id, db_type, final_qty, comment))
                        conn.commit()
                        st.success("Операцію проведено")
                        st.rerun()

    # --- 4. ЖУРНАЛ АУДИТУ (Тільки для Адміністратора) ---
    elif choice == "Журнал аудиту" and st.session_state.user_role == "Адміністратор":
        st.subheader("Історія операцій")
        cursor.execute("""
            SELECT l.id, CONCAT(p.brand, ' ', p.model) AS product, l.operation_type, l.quantity, l.operation_date, l.comment
            FROM operation_logs l
            JOIN products p ON l.product_id = p.id
            ORDER BY l.operation_date DESC
        """)
        logs = cursor.fetchall()
        if logs:
            df_logs = pd.DataFrame(logs)
            df_logs.columns = ["ID", "Товар", "Тип операції", "Кількість", "Дата", "Коментар"]
            st.dataframe(df_logs, hide_index=True, use_container_width=True)
        else:
            st.info("Журнал порожній")

    cursor.close()
    conn.close()
else:
    st.error("Помилка підключення до бази даних")
