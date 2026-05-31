import os
import pymysql
import streamlit as st

def get_db_connection():
    try:
        connection = pymysql.connect(
            host=st.secrets["DB_HOST"],
            port=int(st.secrets["DB_PORT"]),
            user=st.secrets["DB_USER"],
            password=st.secrets["DB_PASSWORD"],
            database=st.secrets["DB_NAME"],
            ssl_verify_cert=False,  
            cursorclass=pymysql.cursors.DictCursor  
        )
        return connection
    except Exception as e:
        st.error(f"Помилка підключення до хмарної бази даних: {e}")
        return None