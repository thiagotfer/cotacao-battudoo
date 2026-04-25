import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="BATTUDOO - Cotação", page_icon="🛒")
st.title("🛒 Sistema de Cotação BATTUDOO")

SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1UCAOUVlT8qbfB-MYRYah0r2jlSIpUNMnQYjPMg_k0ds/edit#gid=0"

ABA_PRODUTOS = "Produtos"
ABA_RESPOSTAS = "Respostas"

try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error("❌ Erro ao carregar o conector.")
    st.write(e)
    st.stop()

def formatar_moeda(texto):
    if not texto:
        return 0.0
    numeros = "".join(filter(str.isdigit, texto))
    return float(numeros) / 100 if numeros else 0.0

try:
    df_produtos = conn.read(
        spreadsheet=SPREADSHEET_URL,
        worksheet=ABA_PRODUTOS,
        ttl=0
    )

    if "Produto" in df_produtos.columns:
        itens_da_semana = df_produtos["Produto"].dropna().tolist()
        st.success("✅ Conectado à Planilha BATTUDOO!")
    else:
        st.error("A coluna A1 precisa se chamar Produto.")
        st.stop()

except Exception as e:
    st.error("❌ Não foi possível ler a aba Produtos.")
    st.stop()

st.write("---")

# --- LÓGICA DE SELEÇÃO DE FORNECEDOR ---
vendedor_selecionado = st.selectbox(
    "Sua Empresa / Fornecedor:",
    ["BATE FORTE", "COMPRE FÁCIL", "SPANI", "ARCON", "ESPERANÇA", "VILA NOVA", "GB", "Outros"]
)

# Se selecionar "Outros", mostramos os campos adicionais
if vendedor_selecionado == "Outros":
    st.info("Por favor, preencha os dados do novo fornecedor abaixo:")
    col_empresa, col_vend, col_tel = st.columns(3)
    with col_empresa:
        empresa_nome = st.text_input("Nome da Empresa")
    with col_vend:
        vendedor_nome = st.text_input("Nome do Vendedor")
    with col_tel:
        telefone = st.text_input("Telefone / WhatsApp")
    
    # Criamos o nome final que será gravado na planilha
    vendedor_final = f"OUTROS: {empresa_nome} | Vend: {vendedor_nome} | Tel: {telefone}"
else:
    vendedor_final = vendedor_selecionado

respostas_vendedor = {}

col1, col2 = st.columns(2)

for i, item in enumerate(itens_da_semana):
    with col1 if i % 2 == 0 else col2:
        entrada = st.text_input(f"{item}:", key=f"in_{item}")
        valor = formatar_moeda(entrada)
        respostas_vendedor[item] = valor
        st.caption(f"Valor: R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

st.write("---")

if st.button("ENVIAR COTAÇÃO", use_container_width=True):
    # Validação: se for "Outros", o nome da empresa é obrigatório
    if vendedor_selecionado == "Outros" and not empresa_nome:
        st.error("⚠️ Para fornecedores novos, o nome da empresa é obrigatório!")
    
    elif any(v > 0 for v in respostas_vendedor.values()):
        with st.spinner("Gravando no Google Sheets..."):
            try:
                try:
                    df_hist = conn.read(
                        spreadsheet=SPREADSHEET_URL,
                        worksheet=ABA_RESPOSTAS,
                        ttl=0
                    )
                except:
                    df_hist = pd.DataFrame()

                nova_linha = {
                    "Data": datetime.now().strftime("%d/%m/%Y %H:%M"),
                    "Fornecedor": vendedor_final, # Grava o nome formatado ou o fixo
                    **respostas_vendedor
                }

                df_final = pd.concat(
                    [df_hist, pd.DataFrame([nova_linha])],
                    ignore_index=True
                )

                conn.update(
                    spreadsheet=SPREADSHEET_URL,
                    worksheet=ABA_RESPOSTAS,
                    data=df_final
                )

                st.success(f"✅ Cotação de {vendedor_final} enviada!")
                st.balloons()

            except Exception as e:
                st.error("❌ Erro ao salvar.")
                st.write(e)
    else:
        st.warning("Preencha pelo menos um valor antes de enviar.")