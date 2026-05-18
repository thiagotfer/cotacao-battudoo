import streamlit as st
import pandas as pd
import urllib.parse
from sqlalchemy import text
from io import BytesIO

# Importação da biblioteca de PDF
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
except ImportError:
    pass

# 1. CONFIGURAÇÃO DA PÁGINA
st.set_page_config(page_title="BATTUDOO Elite v3.9", page_icon="🛒", layout="wide")

# CSS para UI/UX
st.markdown("""
    <style>
    .stNumberInput, .stSelectbox, .stTextInput { margin-top: -5px; }
    hr { margin: 10px 0 !important; }
    .oferta-box { background-color: #fff3cd; color: #000; padding: 15px; border-radius: 10px; border-left: 5px solid #ffc107; margin-bottom: 10px; }
    div[data-testid="stTextArea"] label { display: block !important; }
    </style>
    """, unsafe_allow_html=True)

# 2. CONEXÃO COM O BANCO
try:
    conn = st.connection("postgresql", type="sql")
except Exception as e:
    st.error(f"Erro de conexão: {e}"); st.stop()

# --- FUNÇÕES AUXILIARES ---
def formatar_moeda_input(texto):
    if not texto: return 0.0
    numeros = "".join(filter(str.isdigit, texto))
    return float(numeros) / 100 if numeros else 0.0

def formatar_para_br(valor):
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def gerar_pdf_final(empresa, lista_pedido):
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    p.setFont("Helvetica-Bold", 16)
    p.drawString(70, 750, "BATTUDOO - ESPELHO DE PEDIDO")
    p.setFont("Helvetica", 12)
    p.drawString(70, 725, f"Fornecedor: {empresa}")
    p.drawString(70, 710, f"Data: {pd.Timestamp.now().strftime('%d/%m/%Y %H:%M')}")
    p.line(70, 700, 540, 700)
    y = 670
    p.setFont("Helvetica", 11)
    for linha in lista_pedido:
        p.drawString(70, y, linha)
        y -= 20
        if y < 50: p.showPage(); y = 750
    p.showPage(); p.save(); buffer.seek(0)
    return buffer

# --- NAVEGAÇÃO ---
with st.sidebar:
    st.title("BATTUDOO Admin")
    modo = st.radio("Menu:", ["📝 Cotação", "📊 Painel Admin"], key="nav_main")
    if st.session_state.get('autenticado') and st.button("🔒 Sair"):
        st.session_state.autenticado = False; st.rerun()

# ---------------------------------------------------------
# MODO 1: COTAÇÃO (VENDEDOR)
# ---------------------------------------------------------
if modo == "📝 Cotação":
    st.title("🛒 Portal de Cotação")
    st.markdown("""
        <div style="background-color: #fff4e5; padding: 20px; border-radius: 10px; border-left: 5px solid #ffa500; margin: 10px 0;">
            <strong style="color: #d35400; font-size: 1.2em;">📢 ATENÇÃO:</strong><br>
            <span style="color: #2c3e50; font-weight: 500;">Houve uma mudança no Banco de Dados. Vendedores, por favor, recadastrem-se abaixo.</span>
        </div>
    """, unsafe_allow_html=True)
    
    # SQL CORRIGIDO: Limpo, sem subquery confusa e usando o alias 'AS seller' do jeito certo
    df_v = conn.query("SELECT id, empresa, vendedor AS seller FROM fornecedores ORDER BY empresa", ttl=0)
    lista_v = [f"{r.empresa} ({r.seller})" for r in df_v.itertuples()]
    v_sel = st.selectbox("Selecione sua empresa:", ["---", "🆕 NOVO CADASTRO"] + lista_v)

    f_id = None
    if v_sel == "🆕 NOVO CADASTRO":
        c1, c2, c3 = st.columns(3)
        e, v, z = c1.text_input("Empresa"), c2.text_input("Nome"), c3.text_input("WhatsApp")
        if st.button("Cadastrar"):
            with conn.session as s:
                res = s.execute(text("INSERT INTO fornecedores (empresa, vendedor, whatsapp) VALUES (:e, :v, :z) RETURNING id"), {"e": e.upper(), "v": v, "z": z})
                f_id = res.fetchone()[0]; s.commit(); st.rerun()
    elif v_sel != "---":
        f_id = int(df_v.iloc[lista_v.index(v_sel)]['id'])

    if f_id:
        df_p = conn.query("SELECT id, nome FROM produtos WHERE em_cotacao = TRUE ORDER BY nome", ttl=0)
        if not df_p.empty:
            with st.form("form_cot"):
                res = {}
                for r in df_p.itertuples():
                    c1, c2, c3 = st.columns([3, 1, 2])
                    p_in = c1.text_input(r.nome, key=f"p_{r.id}")
                    res[r.id] = formatar_moeda_input(p_in)
                    c2.write(f"**{formatar_para_br(res[r.id])}**")
                    
                    nome_lower = r.nome.lower()
                    exibir_marca = "+barato" in nome_lower or "+barata" in nome_lower
                    
                    res[f"m_{r.id}"] = c3.text_input("Marca", key=f"m_{r.id}") if exibir_marca else ""
                    
                if st.form_submit_button("🚀 ENVIAR COTAÇÃO"):
                    with conn.session as s:
                        for pid, pr in res.items():
                            if isinstance(pid, int) and pr > 0:
                                s.execute(text("INSERT INTO cotacoes (produto_id, fornecedor_id, preco, marca) VALUES (:p, :f, :pr, :m)"), {"p": pid, "f": f_id, "pr": pr, "m": res.get(f"m_{pid}", "")})
                        s.commit()
                    st.success("Enviado com sucesso!")
                    st.balloons()
                    st.rerun()

        # --- SEÇÃO DE PROMOÇÃO EXTRA (FORA DA LISTA) ---
        st.divider()
        st.subheader("🔥 Ofertas Extras (Produtos fora da lista de cotação)")
        if 'num_o' not in st.session_state: 
            st.session_state.num_o = 1
            
        extras = []
        for i in range(st.session_state.num_o):
            cx1, cx2, cx3 = st.columns([3, 1, 1])
            n_ex = cx1.text_input(f"Produto Extra {i+1}", key=f"ex_n_{i}")
            p_ex = cx2.text_input(f"Preço Extra {i+1}", key=f"ex_p_{i}")
            v_ex = formatar_moeda_input(p_ex)
            cx3.write(f"\n\n**{formatar_para_br(v_ex)}**")
            
            if i == st.session_state.num_o - 1 and n_ex != "":
                st.session_state.num_o += 1; st.rerun()
            if n_ex and v_ex > 0: 
                extras.append({"n": n_ex, "p": v_ex})
        
        if st.button("📢 ENVIAR MEUS EXTRAS"):
            if extras:
                with conn.session as s:
                    for item in extras:
                        s.execute(text("INSERT INTO ofertas_extras (fornecedor_id, produto, preco) VALUES (:f, :n, :p)"), {"f": f_id, "n": item['n'].upper(), "p": item['p']})
                    s.commit()
                st.session_state.num_o = 1
                st.success("Extras enviados com sucesso!")
                st.rerun()
            else:
                st.warning("Preencha ao menos um produto e um preço válidos para enviar.")

# ---------------------------------------------------------
# MODO 2: ADMIN
# ---------------------------------------------------------
else:
    if not st.session_state.get('autenticado'):
        pw = st.text_input("Senha Admin", type="password")
        if st.button("Acessar"):
            if pw == "battudoo2026": st.session_state.autenticado = True; st.rerun()
    else:
        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["🏆 Ranking", "🔍 Consultar Item", "🔥 Extras", "📈 Histórico", "📦 Gestão", "👀 Monitoramento"])
        
        with tab1:
            st.subheader("🏆 Ganhadores da Semana")
            df_r = conn.query("""SELECT DISTINCT ON (c.produto_id) p.nome, c.preco, f.empresa, f.vendedor, c.marca, f.id as forn_id 
                                 FROM cotacoes c JOIN produtos p ON c.produto_id = p.id JOIN fornecedores f ON c.fornecedor_id = f.id 
                                 WHERE p.em_cotacao = TRUE ORDER BY c.produto_id, c.preco ASC""", ttl=0)
            if not df_r.empty:
                for forn in df_r["empresa"].unique():
                    id_f = int(df_r[df_r["empresa"] == forn]["forn_id"].iloc[0])
                    df_f = df_r[df_r["empresa"] == forn]
                    df_ex = conn.query(f"SELECT produto, preco FROM ofertas_extras WHERE fornecedor_id = {id_f}", ttl=0)
                    
                    with st.expander(f"📦 FORNECEDOR: {forn}", expanded=True):
                        linhas = []
                        st.markdown("**Itens Ganhos:**")
                        for _, r in df_f.iterrows():
                            c1, c2, c3, c4, c5 = st.columns([2, 1, 0.7, 0.8, 1.5])
                            p_txt = f"{r['nome']} ({r['marca']})" if r['marca'] else r['nome']
                            c1.write(f"**{p_txt}**"); c2.write(formatar_para_br(r['preco']))
                            qtd = c3.number_input("Qtd", min_value=0, step=1, key=f"q_{id_f}_{r['nome']}", label_visibility="collapsed")
                            und = c4.selectbox("Un", ["UN", "CX", "DP", "PCT", "FD"], key=f"u_{id_f}_{r['nome']}", label_visibility="collapsed")
                            obs = c5.text_input("Obs", key=f"o_{id_f}_{r['nome']}", label_visibility="collapsed")
                            if qtd > 0:
                                texto_item = f"• {qtd} {und} - {p_txt} {f'({obs})' if obs else ''} - {formatar_para_br(r['preco'])}"
                                linhas.append(texto_item)
                        
                        if not df_ex.empty:
                            st.markdown("---")
                            st.markdown("**Ofertas Extras Enviadas pelo Fornecedor:**")
                            for ex in df_ex.itertuples():
                                c1, c2, c3, c4, c5 = st.columns([2, 1, 0.7, 0.8, 1.5])
                                c1.write(f"*{ex.produto}*"); c2.write(formatar_para_br(ex.preco))
                                qe = c3.number_input("Qtd", min_value=0, step=1, key=f"qe_{id_f}_{ex.produto}", label_visibility="collapsed")
                                ue = c4.selectbox("Un", ["UN", "CX", "FD", "PCT"], key=f"ue_{id_f}_{ex.produto}", label_visibility="collapsed")
                                oe = c5.text_input("Obs", key=f"oe_{id_f}_{ex.produto}", label_visibility="collapsed")
                                if qe > 0:
                                    texto_extra = f"• {qe} {ue} - {ex.produto} {f'({oe})' if oe else ''} - {formatar_para_br(ex.preco)} (EXTRA)"
                                    linhas.append(texto_extra)
                        
                        st.divider()
                        col_pdf, col_zap = st.columns(2)
                        zap_msg = f"*PEDIDO BATTUDOO - {forn}*\n\n" + "\n".join(linhas)
                        with col_pdf:
                            if linhas: st.download_button("📄 Gerar PDF", data=gerar_pdf_final(forn, linhas), file_name=f"pedido_{forn}.pdf", key=f"pdf_{id_f}")
                        with col_zap: st.markdown(f"[📲 Zap](https://wa.me/?text={urllib.parse.quote(zap_msg)})")
                        st.code(zap_msg)

        with tab2:
            st.subheader("🔍 Consultar Opções por Item")
            df_p_cota = conn.query("SELECT DISTINCT p.id, p.nome FROM produtos p JOIN cotacoes c ON p.id = c.produto_id WHERE p.em_cotacao = TRUE ORDER BY p.nome", ttl=0)
            if not df_p_cota.empty:
                item_busca = st.selectbox("Selecione o produto:", ["---"] + [r.nome for r in df_p_cota.itertuples()])
                if item_busca != "---":
                    q_todos = """SELECT f.empresa, f.vendedor, c.preco, c.marca, f.whatsapp FROM cotacoes c 
                                 JOIN fornecedores f ON c.fornecedor_id = f.id JOIN produtos p ON c.produto_id = p.id
                                 WHERE p.nome = :nome AND p.em_cotacao = TRUE ORDER BY c.preco ASC"""
                    res_c = conn.query(q_todos, params={"nome": item_busca}, ttl=0)
                    for i, res in enumerate(res_c.itertuples()):
                        cor = "green" if i == 0 else "#2c3e50"
                        st.markdown(f"""<div style="border: 1px solid #ddd; padding: 15px; border-radius: 10px; margin-bottom: 10px; border-left: 10px solid {cor};">
                            <strong style="font-size: 1.1em;">{res.empresa}</strong> | Preço: <b style="color: #d35400;">{formatar_para_br(res.preco)}</b><br>
                            <small>Vendedor: {res.vendedor} | Marca: {res.marca if res.marca else 'N/A'}</small></div>""", unsafe_allow_html=True)
                        if st.button(f"📲 Pedir para {res.empresa}", key=f"z_{i}"):
                            msg = urllib.parse.quote(f"Olá {res.vendedor}, gostaria de fechar o item *{item_busca}* por {formatar_para_br(res.preco)}.")
                            st.markdown(f'<meta http-equiv="refresh" content="0;URL=https://wa.me/{res.whatsapp}?text={msg}">', unsafe_allow_html=True)

        with tab3:
            st.subheader("🔥 Visão Geral de Ofertas Extras")
            df_todas_ex = conn.query("""SELECT f.empresa, f.vendedor, o.produto, o.preco, f.whatsapp 
                                        FROM ofertas_extras o JOIN fornecedores f ON o.fornecedor_id = f.id 
                                        ORDER BY o.produto ASC""", ttl=0)
            if not df_todas_ex.empty:
                st.dataframe(df_todas_ex, use_container_width=True)
            else:
                st.info("Nenhuma oferta extra foi enviada pelos fornecedores ainda.")

        with tab4:
            st.subheader("📈 Histórico")
            h = conn.query("SELECT * FROM historico_precos ORDER BY data_compra DESC", ttl=0)
            st.dataframe(h, use_container_width=True)

        with tab5:
            st.subheader("📦 Gestão")
            with st.form("cad"):
                n = st.text_area("Novos produtos (um por linha):")
                if st.form_submit_button("➕ CADASTRAR"):
                    if n:
                        with conn.session as s:
                            for p in n.split('\n'):
                                if p.strip(): s.execute(text("INSERT INTO produtos (nome, em_cotacao) SELECT :n, FALSE WHERE NOT EXISTS (SELECT 1 FROM produtos WHERE nome = :n)"), {"n": p.strip().upper()})
                            s.commit(); st.rerun()
            st.divider()
            df_g = conn.query("SELECT id, nome, em_cotacao FROM produtos ORDER BY nome", ttl=0)
            with st.form("chk"):
                c = {}; c1, c2 = st.columns(2)
                for i, r in enumerate(df_g.itertuples()):
                    target = c1 if i < len(df_g)/2 else c2
                    with target: c[r.id] = st.checkbox(r.nome, value=bool(r.em_cotacao), key=f"c_{r.id}")
                if st.form_submit_button("✅ ATUALIZAR LISTA ATIVA"):
                    with conn.session as s:
                        for pid, stt in c.items(): s.execute(text("UPDATE produtos SET em_cotacao = :s WHERE id = :i"), {"s": stt, "i": pid})
                    s.commit(); st.rerun()

        with tab6:
            st.subheader("👀 Monitoramento")
            try:
                df_m = conn.query("SELECT f.empresa, MAX(c.data_cadastro) as ultimo FROM fornecedores f JOIN cotacoes c ON f.id = c.fornecedor_id GROUP BY f.empresa", ttl=0)
                st.table(df_m)
            except: st.info("Sem dados.")