import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import urllib.parse

# 1. CONFIGURAÇÃO DA PÁGINA
st.set_page_config(page_title="BATTUDOO Elite", page_icon="🛒", layout="wide")

# CSS para legibilidade e compactação
st.markdown("""
    <style>
    .reportview-container { background: #f0f2f6; }
    .stNumberInput, .stSelectbox, .stTextInput { margin-top: -15px; }
    hr { margin: 5px 0 !important; }
    .stCode { border: 2px solid #007bff !important; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

# URL e Configurações
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1UCAOUVlT8qbfB-MYRYah0r2jlSIpUNMnQYjPMg_k0ds/edit#gid=0"
ABA_PRODUTOS = "Produtos"
ABA_RESPOSTAS = "Respostas"
ABA_VENDEDORES = "Vendedores"

# 2. CONEXÃO
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error(f"Erro de conexão: {e}")
    st.stop()

# FUNÇÕES DE APOIO
def formatar_moeda_input(texto):
    if not texto: return 0.0
    numeros = "".join(filter(str.isdigit, texto))
    return float(numeros) / 100 if numeros else 0.0

def formatar_para_br(valor):
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# 3. NAVEGAÇÃO LATERAL
st.sidebar.title("BATTUDOO Management")
modo = st.sidebar.radio("Navegar para:", ["📝 Cotação (Vendedor)", "📊 Painel Admin (Pedidos)"])

# ---------------------------------------------------------
# MODO 1: COTAÇÃO DO VENDEDOR
# ---------------------------------------------------------
if modo == "📝 Cotação (Vendedor)":
    st.title("🛒 Formulário de Cotação")
    try:
        df_v = conn.read(spreadsheet=SPREADSHEET_URL, worksheet=ABA_VENDEDORES, ttl=0).fillna('')
        vendedores = df_v['Nome'].dropna().tolist() + ["Outros"]
        df_p = conn.read(spreadsheet=SPREADSHEET_URL, worksheet=ABA_PRODUTOS, ttl=0).fillna('')
        itens = df_p["Produto"].dropna().tolist()
    except:
        st.error("Erro ao carregar dados do Sheets.")
        st.stop()

    vendedor_sel = st.selectbox("Sua Empresa:", vendedores)
    
    # LÓGICA PARA NOVOS FORNECEDORES
    if vendedor_sel == "Outros":
        c_emp, c_vend, c_zap = st.columns(3)
        with c_emp: emp = st.text_input("Nome da Empresa", placeholder="Ex: Ambev")
        with c_vend: vend = st.text_input("Seu Nome", placeholder="Ex: João")
        with c_zap: zap = st.text_input("WhatsApp", placeholder="Ex: 1299...")
        vendedor_final = f"{emp.upper()} ({vend} - {zap})"
    else:
        vendedor_final = vendedor_sel

    st.markdown("---")
    respostas = {}

    for item in itens:
        with st.container():
            if "+barato" in item.lower():
                st.info(f"📌 {item}")
                c1, c2 = st.columns(2)
                with c1:
                    p_in = st.text_input(f"Preço {item}", key=f"p_{item}")
                    val = formatar_moeda_input(p_in)
                    respostas[item] = val
                with c2:
                    respostas[f"{item}_MARCA"] = st.text_input(f"Marca", key=f"m_{item}")
            else:
                c1, c2 = st.columns([3, 1])
                with c1:
                    p_in = st.text_input(f"{item}:", key=f"p_{item}")
                    val = formatar_moeda_input(p_in)
                    respostas[item] = val
                with c2:
                    st.write(f"**{formatar_para_br(val)}**")
                respostas[f"{item}_MARCA"] = ""

    if st.button("🚀 ENVIAR PREÇOS"):
        # Validação para 'Outros'
        if vendedor_sel == "Outros" and (not emp or not vend or not zap):
            st.error("Por favor, preencha Empresa, Nome e WhatsApp antes de enviar.")
        elif any(v > 0 for v in respostas.values() if isinstance(v, float)):
            df_h = conn.read(spreadsheet=SPREADSHEET_URL, worksheet=ABA_RESPOSTAS, ttl=0)
            nova_l = {"Data": datetime.now().strftime("%d/%m/%Y %H:%M"), "Fornecedor": vendedor_final, **respostas}
            df_f = pd.concat([df_h, pd.DataFrame([nova_l])], ignore_index=True)
            conn.update(worksheet=ABA_RESPOSTAS, data=df_f)
            st.success(f"✅ Enviado com sucesso como: {vendedor_final}!")
            st.balloons()
        else:
            st.warning("Preencha ao menos um preço.")

# ---------------------------------------------------------
# MODO 2: PAINEL ADMIN (GESTÃO DE PEDIDOS)
# ---------------------------------------------------------
else:
    st.title("📊 Gestão de Pedidos")
    if 'autenticado' not in st.session_state:
        st.session_state.autenticado = False

    if not st.session_state.autenticado:
        senha_in = st.text_input("Senha:", type="password")
        if st.button("Acessar"):
            if senha_in == "battudoo2026":
                st.session_state.autenticado = True
                st.rerun()
            else:
                st.error("Senha incorreta!")
    
    if st.session_state.autenticado:
        if st.sidebar.button("🔒 Sair"):
            st.session_state.autenticado = False
            st.rerun()

        df_res = conn.read(spreadsheet=SPREADSHEET_URL, worksheet=ABA_RESPOSTAS, ttl=0)
        if not df_res.empty:
            cols_prod = [c for c in df_res.columns if c not in ["Data", "Fornecedor"] and not c.endswith("_MARCA")]
            for col in cols_prod:
                df_res[col] = pd.to_numeric(df_res[col], errors='coerce').fillna(0)
            df_res = df_res.fillna('')

            resumo = []
            for prod in cols_prod:
                validos = df_res[df_res[prod] > 0]
                if not validos.empty:
                    idx_min = validos[prod].idxmin()
                    v_row = validos.loc[idx_min]
                    resumo.append({"Produto": prod, "Preço": v_row[prod], "Fornecedor": v_row["Fornecedor"], "Marca": v_row.get(f"{prod}_MARCA", "")})

            if resumo:
                df_ranking = pd.DataFrame(resumo)
                for v in df_ranking["Fornecedor"].unique():
                    with st.expander(f"📦 COMPRAR NO: {v}", expanded=True):
                        itens_v = df_ranking[df_ranking["Fornecedor"] == v]
                        texto_zap = f"*PEDIDO BATTUDOO - {v}*\n\n"
                        total_p = 0.0
                        
                        st.markdown("---")
                        c_h1, c_h2, c_h3, c_h4, c_h5 = st.columns([2.0, 0.8, 0.6, 0.6, 1.0])
                        c_h1.write("**Produto**")
                        c_h2.write("**Preço**")
                        c_h3.write("**Qtd**")
                        c_h4.write("**Und**")
                        c_h5.write("**Obs**")
                        st.markdown("---")

                        for _, row in itens_v.iterrows():
                            c1, c2, c3, c4, c5 = st.columns([2.0, 0.8, 0.6, 0.6, 1.0])
                            with c1:
                                st.markdown(f"**{row['Produto']}**")
                                if row['Marca'] != '': st.caption(f"Marca: {row['Marca']}")
                            with c2:
                                st.write(formatar_para_br(row['Preço']))
                            with c3:
                                qtd = st.number_input("", key=f"q_{v}_{row['Produto']}", min_value=0, step=1, label_visibility="collapsed")
                            with c4:
                                und = st.selectbox("", ["x", "cx", "fd", "dp"], key=f"u_{v}_{row['Produto']}", label_visibility="collapsed")
                            with c5:
                                obs = st.text_input("", key=f"o_{v}_{row['Produto']}", placeholder="Obs", label_visibility="collapsed")
                            
                            if qtd > 0:
                                total_p += (qtd * row['Preço'])
                                marca_limpa = str(row['Marca']).strip()
                                marca_txt = f" ({marca_limpa})" if marca_limpa and marca_limpa.lower() != 'nan' else ""
                                unidade_texto = f"{und}" if und != "x" else "x"
                                obs_limpa = obs.strip()
                                obs_txt = f" {obs_limpa}" if obs_limpa else ""
                                
                                texto_zap += f"• {qtd}{unidade_texto} {row['Produto']}{obs_txt}{marca_txt} - {formatar_para_br(row['Preço'])}\n"
                            st.markdown("<hr>", unsafe_allow_html=True)

                        if total_p > 0:
                            st.write(f"### Total em {v}: {formatar_para_br(total_p)}")
                            st.info("👇 Copie no botão superior direito do quadro azul")
                            st.code(texto_zap, language="text")
                            
                            col_b1, col_b2 = st.columns(2)
                            with col_b1:
                                link = f"https://wa.me/?text={urllib.parse.quote(texto_zap)}"
                                st.markdown(f"""
                                    <a href="{link}" target="_blank" style="text-decoration: none;">
                                        <div style="background-color: #25D366; color: white; padding: 10px; border-radius: 5px; text-align: center; font-weight: bold;">
                                            📲 Enviar p/ WhatsApp
                                        </div>
                                    </a>
                                    """, unsafe_allow_html=True)
                            with col_b2:
                                st.markdown("""
                                    <div style="background-color: #007bff; color: white; padding: 10px; border-radius: 5px; text-align: center; font-weight: bold;">
                                        ⬆️ Copie no quadro azul
                                    </div>
                                    """, unsafe_allow_html=True)
            else:
                st.info("Nenhum preço válido encontrado.")
        else:
            st.info("Aba de respostas está vazia.")