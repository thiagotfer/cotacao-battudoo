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
    st.error("Erro: Biblioteca 'reportlab' não encontrada no ambiente local.")

# 1. CONFIGURAÇÃO DA PÁGINA
st.set_page_config(page_title="BATTUDOO Elite v3.5", page_icon="🛒", layout="wide")

# CSS para melhor UI/UX e compactação de tabelas
st.markdown("""
    <style>
    .stNumberInput, .stSelectbox, .stTextInput { margin-top: -5px; }
    hr { margin: 10px 0 !important; }
    .oferta-box { background-color: #fff3cd; color: #000; padding: 15px; border-radius: 10px; border-left: 5px solid #ffc107; margin-bottom: 10px; }
    .hist-card { background-color: #f8f9fa; padding: 10px; border-radius: 5px; border-bottom: 2px solid #dee2e6; margin-bottom: 5px; color: #333; }
    div[data-testid="stTextArea"] label { display: block !important; }
    </style>
    """, unsafe_allow_html=True)

# 2. CONEXÃO COM O BANCO DE DADOS
try:
    conn = st.connection("postgresql", type="sql")
except Exception as e:
    st.error(f"Erro de conexão com o banco: {e}")
    st.stop()

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
    width, height = letter
    
    # Cabeçalho do PDF
    p.setFont("Helvetica-Bold", 16)
    p.drawString(70, height - 50, "BATTUDOO - ESPELHO DE PEDIDO")
    p.setFont("Helvetica", 12)
    p.drawString(70, height - 75, f"Fornecedor: {empresa}")
    p.drawString(70, height - 90, f"Data: {pd.Timestamp.now().strftime('%d/%m/%Y %H:%M')}")
    p.line(70, height - 100, 540, height - 100)
    
    y = height - 130
    p.setFont("Helvetica", 11)
    
    for linha in lista_pedido:
        p.drawString(70, y, linha)
        y -= 20
        if y < 50:
            p.showPage()
            p.setFont("Helvetica", 11)
            y = height - 50
            
    p.showPage()
    p.save()
    buffer.seek(0)
    return buffer

# --- NAVEGAÇÃO LATERAL ---
with st.sidebar:
    st.title("BATTUDOO Admin")
    modo = st.radio("Menu de Navegação:", ["📝 Cotação", "📊 Painel Admin"], key="nav_main")
    if st.session_state.get('autenticado'):
        st.divider()
        if st.button("🔒 Sair do Sistema"):
            st.session_state.autenticado = False
            st.rerun()

# ---------------------------------------------------------
# MODO 1: COTAÇÃO (VISÃO DO VENDEDOR)
# ---------------------------------------------------------
if modo == "📝 Cotação":
    st.title("🛒 Portal de Cotação")
    
    st.markdown("### 👋 Bem-vindo ao portal BATTUDOO!")
    st.markdown("""
        <div style="background-color: #fff4e5; padding: 15px; border-radius: 10px; border-left: 5px solid #ffa500; margin: 10px 0;">
            <strong style="color: #d35400;">📢 ATENÇÃO:</strong> 
            Houve uma mudança no nosso Banco de Dados, então preciso que todos os vendedores se cadastrem novamente, Obrigado!
        </div>
    """, unsafe_allow_html=True)
    
    df_v = conn.query("SELECT id, empresa, vendedor FROM fornecedores ORDER BY empresa", ttl=0)
    lista_vendedores = [f"{row.empresa} ({row.vendedor})" for row in df_v.itertuples()]
    vendedor_sel = st.selectbox("Identifique-se:", ["---"] + ["🆕 NOVO CADASTRO"] + lista_vendedores)

    forn_id = None
    if vendedor_sel == "🆕 NOVO CADASTRO":
        with st.container():
            c1, c2, c3 = st.columns(3)
            e, v, z = c1.text_input("Nome da Empresa"), c2.text_input("Seu Nome"), c3.text_input("WhatsApp")
            if st.button("Confirmar Cadastro"):
                if e and v:
                    with conn.session as s:
                        res = s.execute(text("INSERT INTO fornecedores (empresa, vendedor, whatsapp) VALUES (:e, :v, :z) RETURNING id"), 
                                        {"e": e.upper(), "v": v, "z": z})
                        forn_id = res.fetchone()[0]; s.commit()
                    st.success("Cadastro realizado!"); st.rerun()
    elif vendedor_sel != "---":
        idx = lista_vendedores.index(vendedor_sel)
        forn_id = int(df_v.iloc[idx]['id'])

    if forn_id:
        df_p = conn.query("SELECT id, nome FROM produtos WHERE em_cotacao = TRUE ORDER BY nome", ttl=0)
        if not df_p.empty:
            with st.form("form_vendedor"):
                st.subheader("📋 Lista de Preços")
                respostas = {}
                for row in df_p.itertuples():
                    tem_b = "+b" in row.nome.lower()
                    c1, c2, c3 = st.columns([3, 1, 2])
                    p_in = c1.text_input(f"{row.nome}", key=f"v_p_{row.id}")
                    respostas[row.id] = formatar_moeda_input(p_in)
                    c2.write(f"**{formatar_para_br(respostas[row.id])}**")
                    respostas[f"m_{row.id}"] = c3.text_input("Marca", key=f"v_m_{row.id}") if tem_b else ""
                
                if st.form_submit_button("🚀 ENVIAR MINHA COTAÇÃO"):
                    with conn.session as s:
                        for p_id, preco in respostas.items():
                            if isinstance(p_id, int) and preco > 0:
                                s.execute(text("INSERT INTO cotacoes (produto_id, fornecedor_id, preco, marca) VALUES (:p, :f, :pr, :m)"),
                                          {"p": p_id, "f": forn_id, "pr": preco, "m": respostas.get(f"m_{p_id}", "")})
                        s.commit()
                    st.success("Cotação enviada!"); st.balloons()
        
        st.divider()
        st.subheader("🔥 Ofertas Extras")
        if 'num_o' not in st.session_state: st.session_state.num_o = 1
        extras = []
        for i in range(st.session_state.num_o):
            cx1, cx2, cx3 = st.columns([3, 1, 1])
            n_ex = cx1.text_input(f"Produto {i+1}", key=f"ex_n_{i}")
            p_ex = cx2.text_input(f"Preço {i+1}", key=f"ex_p_{i}")
            v_ex = formatar_moeda_input(p_ex)
            cx3.write(f"\n\n**{formatar_para_br(v_ex)}**")
            if i == st.session_state.num_o - 1 and n_ex != "":
                st.session_state.num_o += 1; st.rerun()
            if n_ex and v_ex > 0: extras.append({"n": n_ex, "p": v_ex})
        
        if st.button("📢 ENVIAR EXTRAS"):
            with conn.session as s:
                for item in extras:
                    s.execute(text("INSERT INTO ofertas_extras (fornecedor_id, produto, preco) VALUES (:f, :n, :p)"), {"f": forn_id, "n": item['n'], "p": item['p']})
                s.commit()
            st.session_state.num_o = 1; st.success("Extras enviados!"); st.rerun()

# ---------------------------------------------------------
# MODO 2: PAINEL ADMINISTRATIVO
# ---------------------------------------------------------
else:
    if not st.session_state.get('autenticado'):
        with st.form("login"):
            pw = st.text_input("Chave de Acesso Admin", type="password")
            if st.form_submit_button("Entrar"):
                if pw == "battudoo2026": st.session_state.autenticado = True; st.rerun()
                else: st.error("Senha inválida")
    else:
        tab1, tab2, tab3, tab4, tab5 = st.tabs(["🏆 Ranking", "🔥 Extras", "📈 Histórico", "📦 Gestão", "👀 Monitoramento"])

        with tab1:
            st.subheader("🏆 Melhores Preços da Semana")
            q_rank = """SELECT DISTINCT ON (c.produto_id) p.nome, c.preco, f.empresa, f.vendedor, c.marca, f.id as forn_id
                        FROM cotacoes c JOIN produtos p ON c.produto_id = p.id JOIN fornecedores f ON c.fornecedor_id = f.id
                        WHERE p.em_cotacao = TRUE ORDER BY c.produto_id, c.preco ASC;"""
            df_r = conn.query(q_rank, ttl=0)
            
            if not df_r.empty:
                if st.button("💾 SALVAR NO HISTÓRICO"):
                    with conn.session as s:
                        for _, r in df_r.iterrows():
                            s.execute(text("INSERT INTO historico_precos (produto_nome, preco_pago, fornecedor_nome) VALUES (:p, :pr, :f)"), {"p": r['nome'], "pr": r['preco'], "f": r['empresa']})
                        s.commit(); st.success("Histórico atualizado!")

                for forn in df_r["empresa"].unique():
                    id_f = int(df_r[df_r["empresa"] == forn]["forn_id"].iloc[0])
                    df_f = df_r[df_r["empresa"] == forn]
                    df_ex = conn.query(f"SELECT produto, preco FROM ofertas_extras WHERE fornecedor_id = {id_f}", ttl=0)
                    
                    with st.expander(f"📦 FORNECEDOR: {forn}", expanded=True):
                        linhas_pedido = []
                        st.markdown("**Itens Ganhos:**")
                        for _, r in df_f.iterrows():
                            c1, c2, c3, c4, c5 = st.columns([2, 1, 0.7, 0.8, 1.5])
                            p_txt = f"{r['nome']} ({r['marca']})" if r['marca'] else r['nome']
                            c1.write(f"**{p_txt}**"); c2.write(formatar_para_br(r['preco']))
                            qtd = c3.number_input("Qtd", min_value=0, step=1, key=f"q_{id_f}_{r['nome']}", label_visibility="collapsed")
                            und = c4.selectbox("Un", ["UN", "CX", "DP", "PCT", "FD"], key=f"u_{id_f}_{r['nome']}", label_visibility="collapsed")
                            obs = c5.text_input("Obs", key=f"o_{id_f}_{r['nome']}", placeholder="Sabor/Obs", label_visibility="collapsed")
                            if qtd > 0:
                                linhas_pedido.append(f"• {qtd} {und} - {p_txt} {f'({obs})' if obs else ''} - {formatar_para_br(r['preco'])}")

                        if not df_ex.empty:
                            st.markdown("---")
                            for ex in df_ex.itertuples():
                                c1, c2, c3, c4, c5 = st.columns([2, 1, 0.7, 0.8, 1.5])
                                c1.write(f"*{ex.produto}*"); c2.write(formatar_para_br(ex.preco))
                                qe = c3.number_input("Qtd", min_value=0, step=1, key=f"qe_{id_f}_{ex.produto}", label_visibility="collapsed")
                                ue = c4.selectbox("Un", ["UN", "CX", "FD", "PCT"], key=f"ue_{id_f}_{ex.produto}", label_visibility="collapsed")
                                oe = c5.text_input("Obs", key=f"oe_{id_f}_{ex.produto}", placeholder="Sabor", label_visibility="collapsed")
                                if qe > 0:
                                    linhas_pedido.append(f"• {qe} {ue} - {ex.produto} {f'({oe})' if oe else ''} - {formatar_para_br(ex.preco)} (EXTRA)")

                        st.divider()
                        col_pdf, col_zap = st.columns([1, 1])
                        zap_full = f"*PEDIDO BATTUDOO - {forn}*\n\n" + "\n".join(linhas_pedido)
                        
                        with col_pdf:
                            if linhas_pedido:
                                st.download_button("📄 Gerar PDF", data=gerar_pdf_final(forn, linhas_pedido), file_name=f"pedido_{forn}.pdf", mime="application/pdf", key=f"pdf_{id_f}")
                        with col_zap:
                            st.markdown(f"[📲 Enviar WhatsApp](https://wa.me/?text={urllib.parse.quote(zap_full)})")
                        st.code(zap_full)

        with tab4:
            st.subheader("📦 Gestão de Produtos")
            with st.form("cad_novo"):
                n_itens = st.text_area("Cole a lista (um por linha):", placeholder="ARROZ 5KG\nFEIJAO 1KG")
                if st.form_submit_button("➕ CADASTRAR"):
                    if n_itens:
                        with conn.session as s:
                            for p in n_itens.split('\n'):
                                if p.strip(): s.execute(text("INSERT INTO produtos (nome, em_cotacao) SELECT :n, FALSE WHERE NOT EXISTS (SELECT 1 FROM produtos WHERE nome = :n)"), {"n": p.strip().upper()})
                            s.commit(); st.rerun()
            st.divider()
            df_g = conn.query("SELECT id, nome, em_cotacao FROM produtos ORDER BY nome", ttl=0)
            if not df_g.empty:
                with st.form("chk_gest"):
                    c = {}; col1, col2 = st.columns(2)
                    for i, r in enumerate(df_g.itertuples()):
                        target = col1 if i < len(df_g)/2 else col2
                        with target: c[r.id] = st.checkbox(r.nome, value=bool(r.em_cotacao), key=f"c_{r.id}")
                    if st.form_submit_button("✅ ATUALIZAR LISTA ATIVA"):
                        with conn.session as s:
                            for pid, stt in c.items(): s.execute(text("UPDATE produtos SET em_cotacao = :s WHERE id = :i"), {"s": stt, "i": pid})
                            s.commit(); st.rerun()

        with tab5:
            st.subheader("👀 Monitoramento")
            q_m = """SELECT f.empresa, MAX(e.data_envio) as ultimo FROM fornecedores f 
                     JOIN (SELECT fornecedor_id, data_cadastro as data_envio FROM cotacoes) e ON f.id = e.fornecedor_id 
                     GROUP BY f.empresa ORDER BY ultimo DESC"""
            try: st.table(conn.query(q_m, ttl=0))
            except: st.info("Sem envios hoje.")