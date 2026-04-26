import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# 1. CONFIGURAÇÃO DA PÁGINA
st.set_page_config(page_title="BATTUDOO - Gestão", page_icon="🛒", layout="wide")

# URL e Configurações das Abas
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1UCAOUVlT8qbfB-MYRYah0r2jlSIpUNMnQYjPMg_k0ds/edit#gid=0"
ABA_PRODUTOS = "Produtos"
ABA_RESPOSTAS = "Respostas"

# 2. CONEXÃO COM GOOGLE SHEETS
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error("❌ Erro na conexão. Verifique os Secrets no Streamlit Cloud.")
    st.stop()

# FUNÇÕES DE FORMATAÇÃO
def formatar_moeda_input(texto):
    """Trata o input do usuário (ex: '123' vira 1.23)"""
    if not texto: return 0.0
    numeros = "".join(filter(str.isdigit, texto))
    return float(numeros) / 100 if numeros else 0.0

def formatar_para_br(valor):
    """Transforma float em string R$ 0,00"""
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# 3. MENU LATERAL
st.sidebar.title("Navegação BATTUDOO")
modo = st.sidebar.radio("Escolha a função:", ["Enviar Cotação (Vendedor)", "📊 Painel do Gestor (Filtros)"])

# --- MODO 1: FORMULÁRIO DO VENDEDOR ---
if modo == "Enviar Cotação (Vendedor)":
    st.title("🛒 Formulário de Cotação")
    st.info("Vendedor: Digite apenas números para o preço. Ex: '150' para R$ 1,50")

    # Leitura de produtos
    try:
        df_prod = conn.read(spreadsheet=SPREADSHEET_URL, worksheet=ABA_PRODUTOS, ttl=0)
        itens = df_prod["Produto"].dropna().tolist()
    except:
        st.error("Erro ao ler aba 'Produtos'. Verifique a coluna A1.")
        st.stop()

    # Identificação
    lista_forn = ["BATE FORTE", "COMPRE FÁCIL", "SPANI", "ARCON", "ESPERANÇA", "VILA NOVA", "GB", "Outros"]
    vendedor_sel = st.selectbox("Selecione sua Empresa:", lista_forn)
    
    if vendedor_sel == "Outros":
        c_emp, c_vend, c_zap = st.columns(3)
        with c_emp: emp = st.text_input("Empresa")
        with c_vend: vend = st.text_input("Seu Nome")
        with c_zap: zap = st.text_input("WhatsApp")
        vendedor_final = f"OUTROS: {emp} ({vend} - {zap})"
    else:
        vendedor_final = vendedor_sel

    st.markdown("---")
    respostas = {}

    # Gerar campos dinamicamente
    for item in itens:
        if "+barato" in item.lower():
            st.warning(f"📌 Item Especial: {item}")
            c1, c2 = st.columns(2)
            with c1:
                p_input = st.text_input(f"Preço de {item}", key=f"p_{item}")
                v_float = formatar_moeda_input(p_input)
                respostas[item] = v_float
                st.caption(formatar_para_br(v_float))
            with c2:
                respostas[f"{item}_MARCA"] = st.text_input(f"Marca oferecida", key=f"m_{item}", placeholder="Obrigatório")
            st.markdown("---")
        else:
            c1, c2 = st.columns([2, 1])
            with c1:
                p_input = st.text_input(f"{item}:", key=f"p_{item}")
                v_float = formatar_moeda_input(p_input)
                respostas[item] = v_float
            with c2:
                st.write("")
                st.caption(f"Confirmado: {formatar_para_br(v_float)}")
            respostas[f"{item}_MARCA"] = ""

    if st.button("🚀 ENVIAR COTAÇÃO COMPLETA", use_container_width=True):
        if any(v > 0 for v in respostas.values() if isinstance(v, float)):
            with st.spinner("Salvando..."):
                try:
                    df_hist = conn.read(spreadsheet=SPREADSHEET_URL, worksheet=ABA_RESPOSTAS, ttl=0)
                    nova_linha = {"Data": datetime.now().strftime("%d/%m/%Y %H:%M"), "Fornecedor": vendedor_final, **respostas}
                    df_final = pd.concat([df_hist, pd.DataFrame([nova_linha])], ignore_index=True)
                    conn.update(worksheet=ABA_RESPOSTAS, data=df_final)
                    st.success("Enviado com sucesso!")
                    st.balloons()
                except Exception as e:
                    st.error(f"Erro ao salvar: {e}")
        else:
            st.warning("Preencha ao menos um preço.")

# --- MODO 2: PAINEL DO GESTOR ---
elif modo == "📊 Painel do Gestor (Filtros)":
    st.title("📊 Análise de Menores Preços")
    
    senha = st.text_input("Senha de acesso:", type="password")
    if senha == "battudoo2026": # Você pode mudar sua senha aqui
        
        df_res = conn.read(spreadsheet=SPREADSHEET_URL, worksheet=ABA_RESPOSTAS, ttl=0)
        
        if df_res.empty:
            st.warning("Nenhuma cotação encontrada.")
        else:
            # Pegar colunas de produtos (ignora Data, Fornecedor e colunas de Marca)
            cols_prod = [c for c in df_res.columns if c not in ["Data", "Fornecedor"] and not c.endswith("_MARCA")]
            
            melhores_compras = []
            for prod in cols_prod:
                # Apenas preços válidos (maiores que zero)
                validos = df_res[df_res[prod] > 0]
                if not validos.empty:
                    idx_min = validos[prod].idxmin()
                    vencedor = validos.loc[idx_min]
                    melhores_compras.append({
                        "Produto": prod,
                        "Menor Preço": vencedor[prod],
                        "Fornecedor": vencedor["Fornecedor"],
                        "Marca": vencedor.get(f"{prod}_MARCA", "")
                    })

            df_ranking = pd.DataFrame(melhores_compras)

            if not df_ranking.empty:
                st.subheader("📦 Lista de Pedidos por Fornecedor")
                
                vencedores = df_ranking["Fornecedor"].unique()
                for v in vencedores:
                    with st.expander(f"🛒 Pedido para: {v}", expanded=True):
                        # Filtrar itens do fornecedor e formatar visualização
                        itens_v = df_ranking[df_ranking["Fornecedor"] == v].copy()
                        total_v = itens_v["Menor Preço"].sum()
                        
                        # Formatação para exibição na tabela
                        itens_v["Menor Preço"] = itens_v["Menor Preço"].map(formatar_para_br)
                        
                        st.table(itens_v[["Produto", "Menor Preço", "Marca"]])
                        st.write(f"**💰 Total do Pedido: {formatar_para_br(total_v)}**")
                
                st.markdown("---")
                st.subheader("📋 Tabela Geral")
                st.dataframe(df_ranking)
            else:
                st.info("Nenhum preço preenchido nas cotações.")

    elif senha != "":
        st.error("Senha incorreta!")