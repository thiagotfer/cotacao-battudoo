import streamlit as st
import pandas as pd
import urllib.parse
from sqlalchemy import text

# 1. CONFIGURAÇÃO DA PÁGINA
st.set_page_config(page_title="BATTUDOO Elite v2", page_icon="🛒", layout="wide")

# CSS Estilizado para melhor UI/UX
st.markdown("""
    <style>
    .reportview-container { background: #f0f2f6; }
    .stNumberInput, .stSelectbox, .stTextInput { margin-top: -10px; }
    hr { margin: 5px 0 !important; }
    .stCode { border: 2px solid #007bff !important; border-radius: 10px; }
    .oferta-box { 
        background-color: #fff3cd; 
        color: #000000 !important; 
        padding: 15px; 
        border-radius: 10px; 
        border-left: 5px solid #ffc107; 
        margin-bottom: 10px; 
    }
    .hist-card { 
        background-color: #f8f9fa; 
        padding: 10px; 
        border-radius: 5px; 
        border-bottom: 2px solid #dee2e6; 
        margin-bottom: 5px; 
        color: #333; 
    }
    /* Garante visibilidade do label na área de texto */
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
    
    # 1. Linha superior (Cabeçalho)
    st.markdown("### 👋 Bem-vindo a cotação do BATTUDOO!")

    # 2. LINHA DO MEIO (Colorida e com destaque)
    # Usei vermelho (#FF4B4B) para destacar o aviso de recadastro
    st.markdown("""
        <div style="background-color: #ffe9e9; padding: 15px; border-radius: 10px; border-left: 5px solid #ff4b4b; margin: 10px 0;">
            <strong style="color: #ff4b4b;">📢 IMPORTANTE:</strong> 
            <span style="color: #31333f;">Houve uma mudança no nosso Banco de Dados, então preciso que todos os vendedores se cadastrem novamente, Obrigado!</span>
        </div>
    """, unsafe_allow_html=True)

    # 3. Linha inferior (Orientação padrão)
    st.info("""
    Selecione sua empresa abaixo para visualizar os itens da semana. 
    Se você for novo por aqui, escolha a opção **🆕 NOVO CADASTRO**.
    """)
    
    df_v = conn.query("SELECT id, empresa, vendedor FROM fornecedores ORDER BY empresa", ttl=0)
    lista_vendedores = [f"{row.empresa} ({row.vendedor})" for row in df_v.itertuples()]
    vendedor_sel = st.selectbox("Identifique-se:", ["---"] + ["🆕 NOVO CADASTRO"] + lista_vendedores)

    forn_id = None
    if vendedor_sel == "🆕 NOVO CADASTRO":
        with st.container():
            c1, c2, c3 = st.columns(3)
            e = c1.text_input("Nome da Empresa")
            v = c2.text_input("Seu Nome")
            z = c3.text_input("WhatsApp (DDD+Número)")
            if st.button("Confirmar Cadastro"):
                if e and v:
                    with conn.session as s:
                        res = s.execute(text("INSERT INTO fornecedores (empresa, vendedor, whatsapp) VALUES (:e, :v, :z) RETURNING id"), 
                                        {"e": e.upper(), "v": v, "z": z})
                        forn_id = res.fetchone()[0]
                        s.commit()
                    st.success("Cadastro realizado!")
                    st.rerun()
    elif vendedor_sel != "---":
        idx = lista_vendedores.index(vendedor_sel)
        forn_id = int(df_v.iloc[idx]['id'])

    if forn_id:
        # Itens ativos da semana
        df_p = conn.query("SELECT id, nome FROM produtos WHERE em_cotacao = TRUE ORDER BY nome", ttl=0)
        if not df_p.empty:
            with st.form("form_vendedor"):
                st.subheader("📋 Lista de Preços")
                respostas = {}
                for row in df_p.itertuples():
                    tem_b = "+b" in row.nome.lower()
                    if tem_b:
                        st.warning(f"📢 O item **{row.nome}** exige que você informe a **MARCA**.")
                    
                    c1, c2, c3 = st.columns([3, 1, 2])
                    with c1:
                        p_in = st.text_input(f"{row.nome}", key=f"v_p_{row.id}")
                        respostas[row.id] = formatar_moeda_input(p_in)
                    with c2: st.write(f"**{formatar_para_br(respostas[row.id])}**")
                    with c3:
                        if tem_b: respostas[f"m_{row.id}"] = st.text_input("Marca do produto", key=f"v_m_{row.id}")
                        else: respostas[f"m_{row.id}"] = ""
                    st.markdown("<hr style='margin: 10px 0;'>", unsafe_allow_html=True)
                
                if st.form_submit_button("🚀 ENVIAR MINHA COTAÇÃO"):
                    erros = [row.nome for row in df_p.itertuples() if "+b" in row.nome.lower() and respostas.get(row.id, 0) > 0 and not respostas.get(f"m_{row.id}", "")]
                    if erros:
                        st.error(f"❌ Por favor, informe a marca para: {', '.join(erros)}")
                    else:
                        with conn.session as s:
                            for p_id, preco in respostas.items():
                                if isinstance(p_id, int) and preco > 0:
                                    s.execute(text("INSERT INTO cotacoes (produto_id, fornecedor_id, preco, marca) VALUES (:p, :f, :pr, :m)"),
                                              {"p": p_id, "f": forn_id, "pr": preco, "m": respostas.get(f"m_{p_id}", "")})
                            s.commit()
                        st.success("Dados enviados com sucesso!"); st.balloons()
        
        # Ofertas Extras
        st.divider()
        st.subheader("🔥 Tem alguma oferta extra?")
        if 'num_o' not in st.session_state: st.session_state.num_o = 1
        ofertas_list = []
        for i in range(st.session_state.num_o):
            cx1, cx2, cx3 = st.columns([3, 1, 1])
            n_ex = cx1.text_input(f"Produto Extra {i+1}", key=f"ex_n_{i}")
            p_ex = cx2.text_input(f"Preço {i+1}", key=f"ex_p_{i}")
            val_ex = formatar_moeda_input(p_ex)
            cx3.write(f"\n\n**{formatar_para_br(val_ex)}**")
            if i == st.session_state.num_o - 1 and n_ex != "":
                st.session_state.num_o += 1; st.rerun()
            if n_ex and val_ex > 0: ofertas_list.append({"n": n_ex, "p": val_ex})
        
        if st.button("📢 ENVIAR OFERTAS EXTRAS"):
            with conn.session as s:
                for item in ofertas_list:
                    s.execute(text("INSERT INTO ofertas_extras (fornecedor_id, produto, preco) VALUES (:f, :n, :p)"),
                              {"f": forn_id, "n": item['n'], "p": item['p']})
                s.commit()
            st.session_state.num_o = 1
            st.success("Extras enviados!"); st.rerun()

# ---------------------------------------------------------
# MODO 2: PAINEL ADMINISTRATIVO
# ---------------------------------------------------------
else:
    if not st.session_state.get('autenticado'):
        with st.form("login"):
            pw = st.text_input("Chave de Acesso Admin", type="password")
            if st.form_submit_button("Entrar"):
                if pw == "battudoo2026":
                    st.session_state.autenticado = True
                    st.rerun()
                else: st.error("Senha inválida")
    else:
        tab1, tab2, tab3, tab4, tab5 = st.tabs(["🏆 Ranking", "🔥 Extras", "📈 Histórico", "📦 Gestão", "👀 Monitoramento"])

        with tab1:
            st.subheader("🏆 Comparativo de Preços")
            q_rank = """
            SELECT DISTINCT ON (c.produto_id) 
                p.nome, c.preco, f.empresa, c.marca, f.id as forn_id
            FROM cotacoes c 
            JOIN produtos p ON c.produto_id = p.id 
            JOIN fornecedores f ON c.fornecedor_id = f.id
            WHERE p.em_cotacao = TRUE 
            ORDER BY c.produto_id, c.preco ASC;
            """
            df_r = conn.query(q_rank, ttl=0)
            
            if not df_r.empty:
                if st.button("💾 FECHAR SEMANA (SALVAR NO HISTÓRICO)"):
                    with conn.session as s:
                        for _, r in df_r.iterrows():
                            s.execute(text("INSERT INTO historico_precos (produto_nome, preco_pago, fornecedor_nome) VALUES (:p, :pr, :f)"), 
                                      {"p": r['nome'], "pr": r['preco'], "f": r['empresa']})
                        s.commit()
                    st.success("Histórico atualizado!"); st.balloons()

                for forn in df_r["empresa"].unique():
                    id_forn = int(df_r[df_r["empresa"] == forn]["forn_id"].iloc[0])
                    with st.expander(f"📦 GERAR PEDIDO: {forn}", expanded=True):
                        df_itens = df_r[df_r["empresa"] == forn]
                        zap_msg = f"*PEDIDO BATTUDOO - {forn}*\n\n"
                        
                        ch1, ch2, ch3, ch4, ch5 = st.columns([2, 1, 0.8, 0.8, 1.4])
                        ch1.write("**Item**"); ch2.write("**Preço**"); ch3.write("**Qtd**"); ch4.write("**Und**"); ch5.write("**Obs**")
                        
                        for _, r in df_itens.iterrows():
                            c1, c2, c3, c4, c5 = st.columns([2, 1, 0.8, 0.8, 1.4])
                            p_txt = f"{r['nome']} ({r['marca']})" if r['marca'] else r['nome']
                            c1.write(f"**{p_txt}**"); c2.write(formatar_para_br(r['preco']))
                            qtd = c3.number_input("Q", key=f"q_l_{id_forn}_{r['nome']}", min_value=0, step=1, label_visibility="collapsed")
                            und = c4.selectbox("U", ["UN", "CX", "FD", "DP"], key=f"u_l_{id_forn}_{r['nome']}", label_visibility="collapsed")
                            obs = c5.text_input("O", key=f"o_l_{id_forn}_{r['nome']}", placeholder="Obs", label_visibility="collapsed")
                            if qtd > 0:
                                zap_msg += f"• {qtd}{und} {p_txt} {f'({obs})' if obs else ''} - {formatar_para_br(r['preco'])}\n"
                        
                        # Ofertas Extras do mesmo fornecedor
                        df_ex = conn.query(f"SELECT produto, preco FROM ofertas_extras WHERE fornecedor_id = {id_forn}", ttl=0)
                        if not df_ex.empty:
                            st.markdown("---")
                            st.write("🔥 **Extras deste Fornecedor:**")
                            for ex in df_ex.itertuples():
                                ce1, ce2, ce3, ce4, ce5 = st.columns([2, 1, 0.8, 0.8, 1.4])
                                ce1.write(f"**{ex.produto}**"); ce2.write(formatar_para_br(ex.preco))
                                qe = ce3.number_input("Q", key=f"qe_{id_forn}_{ex.produto}", min_value=0, step=1, label_visibility="collapsed")
                                ue = ce4.selectbox("U", ["UN", "CX", "FD"], key=f"ue_{id_forn}_{ex.produto}", label_visibility="collapsed")
                                oe = ce5.text_input("O", key=f"oe_{id_forn}_{ex.produto}", placeholder="Obs", label_visibility="collapsed")
                                if qe > 0:
                                    zap_msg += f"• {qe}{ue} {ex.produto} {f'({oe})' if oe else ''} - {formatar_para_br(ex.preco)} (EXTRA)\n"
                        
                        st.divider(); st.code(zap_msg); st.markdown(f"[📲 Enviar via WhatsApp](https://wa.me/?text={urllib.parse.quote(zap_msg)})")
            else: st.info("Nenhuma cotação ativa no momento.")

        with tab2:
            st.subheader("🔥 Todas as Ofertas Extras")
            if st.button("🗑️ Limpar Banco de Extras"):
                with conn.session as s: s.execute(text("TRUNCATE TABLE ofertas_extras RESTART IDENTITY")); s.commit()
                st.rerun()
            df_o = conn.query("SELECT o.produto, o.preco, f.empresa FROM ofertas_extras o JOIN fornecedores f ON o.fornecedor_id = f.id", ttl=0)
            if not df_o.empty:
                for _, r in df_o.iterrows():
                    st.markdown(f'<div class="oferta-box"><strong>{r["empresa"]}</strong>: {r["produto"]} - {formatar_para_br(r["preco"])}</div>', unsafe_allow_html=True)

        with tab3:
            st.subheader("📈 Histórico de Compras")
            h_busca = st.text_input("🔍 Pesquisar no Histórico:", placeholder="Ex: Arroz").upper()
            df_h = conn.query("SELECT produto_nome, preco_pago, fornecedor_nome, data_compra FROM historico_precos ORDER BY data_compra DESC", ttl=0)
            if not df_h.empty:
                if h_busca: df_h = df_h[df_h['produto_nome'].str.contains(h_busca, na=False)]
                for _, r in df_h.iterrows():
                    st.markdown(f'<div class="hist-card"><strong>{r["produto_nome"]}</strong>: {formatar_para_br(r["preco_pago"])} <br><small>🛒 {r["fornecedor_nome"]} | 📅 {r["data_compra"].strftime("%d/%m/%Y")}</small></div>', unsafe_allow_html=True)

        with tab4:
            st.subheader("📦 Gestão de Produtos")
            with st.form("cad_form"):
                st.write("##### Cadastrar Novos Itens")
                txt_n = st.text_area("Um item por linha:", placeholder="SABÃO OMO\nCAFÉ PILÃO")
                if st.form_submit_button("➕ SALVAR NO BANCO"):
                    if txt_n:
                        with conn.session as s:
                            for p in txt_n.split('\n'):
                                if p.strip():
                                    s.execute(text("INSERT INTO produtos (nome, em_cotacao) SELECT :n, FALSE WHERE NOT EXISTS (SELECT 1 FROM produtos WHERE nome = :n)"), {"n": p.strip().upper()})
                            s.commit(); st.rerun()
            st.divider()
            st.markdown("##### Selecionar Lista da Semana")
            b_gest = st.text_input("🔍 Filtrar para Seleção:", key="bg").upper()
            df_full = conn.query("SELECT id, nome, em_cotacao FROM produtos ORDER BY nome", ttl=0)
            if not df_full.empty:
                df_fil = df_full[df_full['nome'].str.contains(b_gest, na=False)] if b_gest else df_full
                with st.form("check_form"):
                    checks = {}; c1, c2 = st.columns(2)
                    for i, r in enumerate(df_fil.itertuples()):
                        target = c1 if i < len(df_fil)/2 else c2
                        with target: checks[r.id] = st.checkbox(r.nome, value=bool(r.em_cotacao), key=f"c_{r.id}")
                    if st.form_submit_button("✅ ATUALIZAR LISTA ATIVA"):
                        with conn.session as s:
                            for pid, stt in checks.items():
                                s.execute(text("UPDATE produtos SET em_cotacao = :s WHERE id = :i"), {"s": stt, "i": pid})
                            s.commit(); st.rerun()
            if st.button("🧹 Desativar Tudo (Zerar Lista)", use_container_width=True):
                with conn.session as s: s.execute(text("UPDATE produtos SET em_cotacao = FALSE")); s.commit(); st.rerun()

        with tab5:
            st.subheader("👀 Monitoramento de Envio")
            # Unifica o monitoramento de cotações e extras
            q_mon = """
                SELECT f.empresa, f.vendedor, MAX(data_envio) as ultimo_envio 
                FROM fornecedores f 
                LEFT JOIN (
                    SELECT fornecedor_id, data_cadastro as data_envio FROM cotacoes
                    UNION ALL
                    SELECT fornecedor_id, data_cadastro as data_envio FROM ofertas_extras
                ) envios ON f.id = envios.fornecedor_id
                WHERE data_envio IS NOT NULL
                GROUP BY f.empresa, f.vendedor 
                ORDER BY ultimo_envio DESC
            """
            try:
                df_mon = conn.query(q_mon, ttl=0)
                if not df_mon.empty:
                    df_mon['ultimo_envio'] = pd.to_datetime(df_mon['ultimo_envio']).dt.strftime('%d/%m/%Y %H:%M:%S')
                    st.table(df_mon)
                else: st.info("Nenhum envio registrado hoje.")
            except: st.warning("Certifique-se de que as tabelas possuem a coluna 'data_cadastro'.")