import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# 1. CONFIGURAÇÃO DA PÁGINA
st.set_page_config(page_title="BATTUDOO - Cotação", page_icon="🛒", layout="centered")

st.title("🛒 Sistema de Cotação BATTUDOO")
st.markdown("---")

# URL e Configurações das Abas
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1UCAOUVlT8qbfB-MYRYah0r2jlSIpUNMnQYjPMg_k0ds/edit#gid=0"
ABA_PRODUTOS = "Produtos"
ABA_RESPOSTAS = "Respostas"

# 2. CONEXÃO COM GOOGLE SHEETS (Usa os Secrets configurados)
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error("❌ Erro na conexão. Verifique os Secrets no Streamlit Cloud.")
    st.stop()

# 3. FUNÇÃO PARA TRATAR VALORES MONETÁRIOS
def formatar_moeda(texto):
    if not texto: return 0.0
    numeros = "".join(filter(str.isdigit, texto))
    return float(numeros) / 100 if numeros else 0.0

# 4. LEITURA DA LISTA DE PRODUTOS
try:
    df_produtos = conn.read(spreadsheet=SPREADSHEET_URL, worksheet=ABA_PRODUTOS, ttl=0)
    if "Produto" in df_produtos.columns:
        itens_da_semana = df_produtos["Produto"].dropna().tolist()
    else:
        st.error("A coluna A1 da aba 'Produtos' deve se chamar 'Produto'.")
        st.stop()
except Exception as e:
    st.error(f"❌ Erro ao carregar produtos: {e}")
    st.stop()

# 5. IDENTIFICAÇÃO DO FORNECEDOR
st.subheader("📝 Identificação")
lista_fornecedores = ["BATE FORTE", "COMPRE FÁCIL", "SPANI", "ARCON", "ESPERANÇA", "VILA NOVA", "GB", "Outros"]
vendedor_selecionado = st.selectbox("Selecione sua Empresa / Fornecedor:", lista_fornecedores)

if vendedor_selecionado == "Outros":
    col_e, col_v, col_t = st.columns(3)
    with col_e: empresa = st.text_input("Nome da Empresa")
    with col_v: nome_vend = st.text_input("Seu Nome")
    with col_t: fone = st.text_input("WhatsApp")
    vendedor_final = f"OUTROS: {empresa} ({nome_vend} - {fone})"
else:
    vendedor_final = vendedor_selecionado

st.markdown("---")

# 6. FORMULÁRIO DINÂMICO (Lógica +Barato)
st.subheader("💰 Tabela de Preços")
respostas_vendedor = {}

for item in itens_da_semana:
    # Verifica se o item deve pedir a marca
    if "+barato" in item.lower():
        with st.container():
            st.warning(f"📌 Item Especial: {item}")
            c1, c2 = st.columns(2)
            with c1:
                entrada = st.text_input(f"Preço de {item}", key=f"p_{item}")
                valor = formatar_moeda(entrada)
                respostas_vendedor[item] = valor
                st.caption(f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
            with c2:
                marca = st.text_input(f"Qual marca você oferece?", key=f"m_{item}", placeholder="Ex: Omo, Ypê...")
                respostas_vendedor[f"{item}_MARCA"] = marca
            st.markdown("---")
    else:
        # Itens padrão
        c1, c2 = st.columns([1.5, 1])
        with c1:
            entrada = st.text_input(f"{item}:", key=f"p_{item}")
            valor = formatar_moeda(entrada)
            respostas_vendedor[item] = valor
        with c2:
            # Espaço visual para alinhar ou informação extra se desejar
            st.write("") 
            st.caption(f"Confirmado: R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        respostas_vendedor[f"{item}_MARCA"] = "" # Campo marca vazio na planilha

st.write("---")

# 7. BOTÃO DE ENVIO
if st.button("🚀 ENVIAR COTAÇÃO", use_container_width=True):
    # Validações
    if vendedor_selecionado == "Outros" and not empresa:
        st.warning("⚠️ Identifique sua empresa para continuar.")
    elif any(v > 0 for v in respostas_vendedor.values() if isinstance(v, (int, float))):
        with st.spinner("Gravando no Google Sheets..."):
            try:
                # Lê histórico
                try:
                    df_hist = conn.read(spreadsheet=SPREADSHEET_URL, worksheet=ABA_RESPOSTAS, ttl=0)
                except:
                    df_hist = pd.DataFrame()

                # Prepara linha
                nova_linha = {
                    "Data": datetime.now().strftime("%d/%m/%Y %H:%M"),
                    "Fornecedor": vendedor_final,
                    **respostas_vendedor
                }

                # Salva
                df_final = pd.concat([df_hist, pd.DataFrame([nova_linha])], ignore_index=True)
                conn.update(worksheet=ABA_RESPOSTAS, data=df_final)

                st.success(f"✅ Cotação de {vendedor_final} enviada com sucesso!")
                st.balloons()
            except Exception as e:
                st.error(f"❌ Erro ao salvar: {e}")
    else:
        st.warning("⚠️ Preencha pelo menos um valor.")