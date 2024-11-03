# Streamlit API Reference:
# https://docs.streamlit.io/develop/api-reference
import streamlit as st
import pandas as pd

st.title("My Awesome Streamlit App")

col1, col2 = st.columns(2)

with col1:
    st.header("Column 1")
    name = st.text_input("Enter your name: ")
    st.button("Click me")
    st.link_button("Click **me** too!", url="/profile")

with col2:
    st.header("Column 2")
    if name:
        st.write(f"Hello, **{name}**, welcome!")
        st.metric("Your name", name)
        st.metric("Number of characters in your name", len(name))


df = pd.read_csv("https://raw.githubusercontent.com/dataprofessor/data/master/penguins_cleaned.csv")
st.dataframe(df)