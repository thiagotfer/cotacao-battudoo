import streamlit as st
import pandas as pd
import urllib.parse
from sqlalchemy import text
from io import BytesIO

# Importação da biblioteca de PDF
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    REPORTLAB_OK = True
except ImportError:
    REPORTLAB_OK = False

# ---------------------------------------------------------
# 1. CONFIGURAÇÃO DA PÁGINA
# ---------------------------------------------------------
st.set_page_config(page_title="BIGBERG 2 Elite v4.3", page_icon="🛒", layout="wide")

st.markdown(
    """
    <style>
    .stNumberInput, .stSelectbox, .stTextInput { margin-top: -5px; }
    hr { margin: 10px 0 !important; }
    .oferta-box {
        background-color: #fff3cd;
        color: #000;
        padding: 15px;
        border-radius: 10px;
        border-left: 5px solid #ffc107;
        margin-bottom: 10px;
    }
    div[data-testid="stTextArea"] label { display: block !important; }
    .small-muted { color: #666; font-size: 0.9em; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------
# 2. CONEXÃO COM O BANCO
# ---------------------------------------------------------
try:
    conn = st.connection("postgresql", type="sql")
except Exception as e:
    st.error(f"Erro de conexão: {e}")
    st.stop()

# ---------------------------------------------------------
# 3. CONFIGURAÇÕES GERAIS
# ---------------------------------------------------------
UNIDADES_PEDIDO = [
    "UN",
    "CX",
    "PCT",
    "FD",
    "DZ",
    "CARTELA",
    "KG",
    "SC",
    "BDJ",
    "DP",
]

try:
    ADMIN_PASSWORD = st.secrets.get("ADMIN_PASSWORD", "battudoo2026")
except Exception:
    ADMIN_PASSWORD = "battudoo2026"

# ---------------------------------------------------------
# 4. FUNÇÕES AUXILIARES
# ---------------------------------------------------------
def formatar_moeda_input(texto):
    """Converte o texto digitado em preço.
    Mantém o comportamento antigo: 1890 vira 18,90.
    """
    if not texto:
        return 0.0
    numeros = "".join(filter(str.isdigit, str(texto)))
    return float(numeros) / 100 if numeros else 0.0


def formatar_para_br(valor):
    try:
        return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0,00"


def normalizar_lista_produtos(texto):
    """Recebe texto com um produto por linha, remove vazios e duplicados mantendo a ordem."""
    produtos = []
    vistos = set()

    for linha in texto.splitlines():
        nome = linha.strip().upper()
        if not nome:
            continue

        chave = " ".join(nome.split())
        if chave not in vistos:
            produtos.append(chave)
            vistos.add(chave)

    return produtos


def gerar_pdf_final(empresa, lista_pedido):
    if not REPORTLAB_OK:
        return BytesIO(b"ReportLab nao instalado. Adicione reportlab ao requirements.txt")

    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    p.setFont("Helvetica-Bold", 16)
    p.drawString(70, 750, "BIGBERG 2 (CPV VELHA) - ESPELHO DE PEDIDO")
    p.setFont("Helvetica", 12)
    p.drawString(70, 725, f"Fornecedor: {empresa}")
    p.drawString(70, 710, f"Data: {pd.Timestamp.now().strftime('%d/%m/%Y %H:%M')}")
    p.line(70, 700, 540, 700)
    y = 670
    p.setFont("Helvetica", 10)

    if lista_pedido:
        for linha in lista_pedido:
            # Evita linha muito longa estourando no PDF
            texto = str(linha)
            if len(texto) > 95:
                texto = texto[:92] + "..."
            p.drawString(70, y, texto)
            y -= 18
            if y < 50:
                p.showPage()
                y = 750
                p.setFont("Helvetica", 10)
    else:
        p.drawString(70, y, "Nenhum item com quantidade informada para este pedido.")

    p.showPage()
    p.save()
    buffer.seek(0)
    return buffer


def ativar_ou_cadastrar_produtos(produtos, limpar_antes=False):
    """Cadastra produtos que não existem e marca todos da lista como em_cotacao = TRUE."""
    inseridos = 0
    atualizados = 0

    with conn.session as s:
        if limpar_antes:
            s.execute(text("UPDATE produtos SET em_cotacao = FALSE WHERE em_cotacao = TRUE"))

        for nome_produto in produtos:
            existe = s.execute(
                text(
                    """
                    SELECT id
                    FROM produtos
                    WHERE UPPER(TRIM(nome)) = UPPER(TRIM(:nome))
                    LIMIT 1
                    """
                ),
                {"nome": nome_produto},
            ).fetchone()

            if existe:
                s.execute(
                    text("UPDATE produtos SET em_cotacao = TRUE WHERE id = :id"),
                    {"id": existe[0]},
                )
                atualizados += 1
            else:
                s.execute(
                    text("INSERT INTO produtos (nome, em_cotacao) VALUES (:nome, TRUE)"),
                    {"nome": nome_produto},
                )
                inseridos += 1

        s.commit()

    return inseridos, atualizados


def tirar_todos_produtos_da_cotacao():
    with conn.session as s:
        s.execute(text("UPDATE produtos SET em_cotacao = FALSE WHERE em_cotacao = TRUE"))
        s.commit()


def encerrar_cotacao_atual():
    """Limpa a cotação atual por completo.
    Não apaga cadastro de produtos nem fornecedores.
    """
    with conn.session as s:
        s.execute(text("DELETE FROM cotacoes"))
        s.execute(text("DELETE FROM ofertas_extras"))
        s.execute(text("UPDATE produtos SET em_cotacao = FALSE WHERE em_cotacao = TRUE"))
        s.commit()


def render_botao_encerrar_cotacao(local_key):
    st.markdown("### 🧹 Encerrar / limpar cotação atual")
    st.warning(
        "Use esta opção só quando a cotação da semana já tiver acabado. "
        "Ela apaga os preços enviados e as ofertas extras da cotação atual, "
        "mas não apaga produtos nem fornecedores."
    )

    confirmar = st.checkbox(
        "Confirmo que quero apagar os preços enviados, as ofertas extras e tirar todos os produtos da cotação.",
        key=f"confirmar_encerrar_{local_key}",
    )

    if st.button("🗑️ ENCERRAR E APAGAR COTAÇÃO ATUAL", key=f"encerrar_{local_key}"):
        if not confirmar:
            st.warning("Marque a confirmação antes de encerrar a cotação.")
        else:
            encerrar_cotacao_atual()
            st.session_state.pedidos_manuais = {}
            st.success("Cotação atual encerrada e limpa com sucesso.")
            st.rerun()


def get_pedidos_manuais():
    """Itens adicionados pela aba Consultar Item.
    Fica salvo durante a sessão do navegador e não mexe nas chaves dos widgets do Ranking,
    evitando crash do Streamlit ao tentar alterar um campo já renderizado.
    """
    if "pedidos_manuais" not in st.session_state:
        st.session_state.pedidos_manuais = {}
    return st.session_state.pedidos_manuais


def adicionar_item_pedido_manual(
    fornecedor_id,
    empresa,
    produto_id,
    produto,
    preco,
    marca,
    quantidade,
    unidade,
    observacao,
    cotacao_id=None,
):
    pedidos = get_pedidos_manuais()
    chave_fornecedor = str(int(fornecedor_id))

    item = {
        "cotacao_id": int(cotacao_id) if cotacao_id is not None else None,
        "fornecedor_id": int(fornecedor_id),
        "empresa": str(empresa),
        "produto_id": int(produto_id) if produto_id is not None else None,
        "produto": str(produto),
        "preco": float(preco),
        "marca": str(marca or ""),
        "quantidade": int(quantidade),
        "unidade": str(unidade),
        "observacao": str(observacao or ""),
    }

    if chave_fornecedor not in pedidos:
        pedidos[chave_fornecedor] = []

    # Se clicar de novo no mesmo item, atualiza em vez de duplicar.
    atualizado = False
    for idx, existente in enumerate(pedidos[chave_fornecedor]):
        if cotacao_id is not None and existente.get("cotacao_id") == int(cotacao_id):
            pedidos[chave_fornecedor][idx] = item
            atualizado = True
            break

    if not atualizado:
        pedidos[chave_fornecedor].append(item)

    st.session_state.pedidos_manuais = pedidos
    return atualizado


def remover_item_pedido_manual(fornecedor_id, indice):
    pedidos = get_pedidos_manuais()
    chave_fornecedor = str(int(fornecedor_id))
    if chave_fornecedor in pedidos and 0 <= indice < len(pedidos[chave_fornecedor]):
        pedidos[chave_fornecedor].pop(indice)
        if not pedidos[chave_fornecedor]:
            pedidos.pop(chave_fornecedor, None)
        st.session_state.pedidos_manuais = pedidos


def limpar_pedido_manual_fornecedor(fornecedor_id):
    pedidos = get_pedidos_manuais()
    pedidos.pop(str(int(fornecedor_id)), None)
    st.session_state.pedidos_manuais = pedidos


def montar_texto_item_manual(item):
    produto_txt = item["produto"]
    if item.get("marca"):
        produto_txt = f"{produto_txt} ({item['marca']})"

    obs_txt = f" ({item['observacao']})" if item.get("observacao") else ""
    return (
        f"• {item['quantidade']} {item['unidade']} - "
        f"{produto_txt}{obs_txt} - {formatar_para_br(item['preco'])}"
    )


# ---------------------------------------------------------
# 5. NAVEGAÇÃO
# ---------------------------------------------------------
with st.sidebar:
    st.title("BIG BERG 2 Admin")
    modo = st.radio("Menu:", ["📝 Cotação", "📊 Painel Admin"], key="nav_main")

    if st.session_state.get("autenticado") and st.button("🔒 Sair"):
        st.session_state.autenticado = False
        st.rerun()

# ---------------------------------------------------------
# MODO 1: COTAÇÃO (VENDEDOR)
# ---------------------------------------------------------
if modo == "📝 Cotação":
    st.title("🛒 Portal de Cotação")

    st.markdown(
        """
        <div style="background-color: #fff4e5; padding: 20px; border-radius: 10px; border-left: 5px solid #ffa500; margin: 10px 0;">
            <strong style="color: #d35400; font-size: 1.2em;">📢 ATENÇÃO:</strong><br>
            <span style="color: #2c3e50; font-weight: 500;">Cadastre-se abaixo se necessário e preencha apenas os itens que deseja cotar.</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    df_v = conn.query(
        "SELECT id, empresa, vendedor AS seller FROM fornecedores ORDER BY empresa, vendedor",
        ttl=30,
    )
    lista_v = [f"{r.empresa} ({r.seller})" for r in df_v.itertuples()]
    v_sel = st.selectbox("Selecione sua empresa:", ["---", "🆕 NOVO CADASTRO"] + lista_v)

    f_id = None
    if v_sel == "🆕 NOVO CADASTRO":
        c1, c2, c3 = st.columns(3)
        e = c1.text_input("Empresa")
        v = c2.text_input("Nome")
        z = c3.text_input("WhatsApp")

        if st.button("Cadastrar"):
            if not e.strip() or not v.strip():
                st.warning("Preencha pelo menos empresa e nome do vendedor.")
            else:
                with conn.session as s:
                    res = s.execute(
                        text(
                            """
                            INSERT INTO fornecedores (empresa, vendedor, whatsapp)
                            VALUES (:e, :v, :z)
                            RETURNING id
                            """
                        ),
                        {"e": e.strip().upper(), "v": v.strip(), "z": z.strip()},
                    )
                    f_id = res.fetchone()[0]
                    s.commit()
                st.success("Cadastro realizado. Selecione sua empresa na lista para cotar.")
                st.rerun()
    elif v_sel != "---":
        f_id = int(df_v.iloc[lista_v.index(v_sel)]["id"])

    if f_id:
        df_p = conn.query(
            "SELECT id, nome FROM produtos WHERE em_cotacao = TRUE ORDER BY nome",
            ttl=0,
        )

        if df_p.empty:
            st.info("Nenhum produto está ativo para cotação no momento.")
        else:
            st.caption(f"Produtos em cotação: {len(df_p)}")

            with st.form("form_cot"):
                res = {}

                for r in df_p.itertuples():
                    c1, c2, c3 = st.columns([3, 1, 2])
                    p_in = c1.text_input(r.nome, key=f"p_{r.id}")
                    res[r.id] = formatar_moeda_input(p_in)
                    c2.write(f"**{formatar_para_br(res[r.id])}**")

                    nome_para_busca = str(r.nome).lower()
                    exibir_marca = (
                        "barato" in nome_para_busca
                        or "barata" in nome_para_busca
                        or "marca" in nome_para_busca
                    )

                    if exibir_marca:
                        res[f"m_{r.id}"] = c3.text_input(
                            "⚠️ Digite a marca deste item",
                            key=f"m_{r.id}",
                            placeholder="Ex: Nestlé / Renata",
                        )
                    else:
                        res[f"m_{r.id}"] = ""

                if st.form_submit_button("🚀 ENVIAR COTAÇÃO"):
                    enviados = 0
                    with conn.session as s:
                        for pid, pr in res.items():
                            if isinstance(pid, int) and pr > 0:
                                s.execute(
                                    text(
                                        """
                                        INSERT INTO cotacoes
                                            (produto_id, fornecedor_id, preco, marca, data_cotacao, data_cadastro)
                                        VALUES
                                            (:p, :f, :pr, :m, NOW(), NOW())
                                        ON CONFLICT (produto_id, fornecedor_id)
                                        DO UPDATE SET
                                            preco = EXCLUDED.preco,
                                            marca = EXCLUDED.marca,
                                            data_cotacao = NOW(),
                                            data_cadastro = NOW()
                                        """
                                    ),
                                    {
                                        "p": pid,
                                        "f": f_id,
                                        "pr": pr,
                                        "m": res.get(f"m_{pid}", ""),
                                    },
                                )
                                enviados += 1
                        s.commit()

                    st.success(f"Cotação enviada com sucesso! Itens enviados: {enviados}")
                    st.balloons()
                    st.rerun()

        # --- SEÇÃO DE PROMOÇÃO EXTRA (FORA DA LISTA) ---
        st.divider()
        st.subheader("🔥 Ofertas Extras (produtos fora da lista de cotação)")
        st.caption("Use esta área para ofertas que não estavam na lista oficial da semana.")

        qtd_extras = st.number_input(
            "Quantas ofertas extras deseja enviar?",
            min_value=1,
            max_value=20,
            value=1,
            step=1,
            key="qtd_extras_vendedor",
        )

        extras = []
        for i in range(int(qtd_extras)):
            cx1, cx2, cx3 = st.columns([3, 1, 1])
            n_ex = cx1.text_input(f"Produto Extra {i + 1}", key=f"ex_n_{i}")
            p_ex = cx2.text_input(f"Preço Extra {i + 1}", key=f"ex_p_{i}")
            v_ex = formatar_moeda_input(p_ex)
            cx3.write(f"\n\n**{formatar_para_br(v_ex)}**")

            if n_ex.strip() and v_ex > 0:
                extras.append({"n": n_ex.strip().upper(), "p": v_ex})

        if st.button("📢 ENVIAR MEUS EXTRAS"):
            if extras:
                with conn.session as s:
                    for item in extras:
                        s.execute(
                            text(
                                """
                                INSERT INTO ofertas_extras (fornecedor_id, produto, preco)
                                VALUES (:f, :n, :p)
                                """
                            ),
                            {"f": f_id, "n": item["n"], "p": item["p"]},
                        )
                    s.commit()

                st.success(f"Extras enviados com sucesso! Total: {len(extras)}")
                st.rerun()
            else:
                st.warning("Preencha ao menos um produto e um preço válido para enviar.")

# ---------------------------------------------------------
# MODO 2: ADMIN
# ---------------------------------------------------------
else:
    if not st.session_state.get("autenticado"):
        pw = st.text_input("Senha Admin", type="password")
        if st.button("Acessar"):
            if pw == ADMIN_PASSWORD:
                st.session_state.autenticado = True
                st.rerun()
            else:
                st.error("Senha incorreta.")
    else:
        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
            [
                "🏆 Ranking",
                "🔍 Consultar Item",
                "🔥 Extras",
                "📈 Histórico",
                "📦 Gestão",
                "👀 Monitoramento",
            ]
        )

        # -------------------------------------------------
        # TAB 1: RANKING / PEDIDO
        # -------------------------------------------------
        with tab1:
            st.subheader("🏆 Ganhadores da Semana")

            df_r = conn.query(
                """
                SELECT DISTINCT ON (c.produto_id)
                    p.id AS produto_id,
                    p.nome,
                    c.preco,
                    f.empresa,
                    f.vendedor,
                    COALESCE(c.marca, '') AS marca,
                    f.id AS forn_id
                FROM cotacoes c
                JOIN produtos p ON c.produto_id = p.id
                JOIN fornecedores f ON c.fornecedor_id = f.id
                WHERE p.em_cotacao = TRUE
                ORDER BY c.produto_id, c.preco ASC, c.data_cotacao DESC
                """,
                ttl=0,
            )

            if df_r.empty:
                st.info("Ainda não há cotações enviadas para os produtos ativos.")
            else:
                for forn in df_r["empresa"].unique():
                    id_f = int(df_r[df_r["empresa"] == forn]["forn_id"].iloc[0])
                    df_f = df_r[df_r["empresa"] == forn]
                    df_ex = conn.query(
                        """
                        SELECT id, produto, preco
                        FROM ofertas_extras
                        WHERE fornecedor_id = :fornecedor_id
                        ORDER BY produto ASC, id ASC
                        """,
                        params={"fornecedor_id": id_f},
                        ttl=0,
                    )

                    with st.expander(f"📦 FORNECEDOR: {forn}", expanded=True):
                        linhas = []
                        linhas_pdf_conferencia = []

                        st.markdown("**Itens ganhos:**")
                        for _, r in df_f.iterrows():
                            c1, c2, c3, c4, c5 = st.columns([2, 1, 0.7, 0.9, 1.5])

                            p_txt = f"{r['nome']} ({r['marca']})" if r["marca"] else r["nome"]
                            c1.write(f"**{p_txt}**")
                            c2.write(formatar_para_br(r["preco"]))

                            produto_id = int(r["produto_id"])
                            qtd = c3.number_input(
                                "Qtd",
                                min_value=0,
                                step=1,
                                key=f"q_{id_f}_{produto_id}",
                                label_visibility="collapsed",
                            )
                            und = c4.selectbox(
                                "Un",
                                UNIDADES_PEDIDO,
                                key=f"u_{id_f}_{produto_id}",
                                label_visibility="collapsed",
                            )
                            obs = c5.text_input(
                                "Obs",
                                key=f"o_{id_f}_{produto_id}",
                                label_visibility="collapsed",
                            )

                            linhas_pdf_conferencia.append(
                                f"• [  ] - {p_txt} - {formatar_para_br(r['preco'])}"
                            )

                            if qtd > 0:
                                texto_item = (
                                    f"• {qtd} {und} - {p_txt} "
                                    f"{f'({obs})' if obs else ''} - {formatar_para_br(r['preco'])}"
                                )
                                linhas.append(texto_item)

                        # BLOCO DE EXTRAS INTEGRADO AO ESPELHO
                        if not df_ex.empty:
                            st.markdown("---")
                            st.markdown("**Ofertas extras enviadas pelo fornecedor:**")

                            for ex in df_ex.itertuples():
                                c1, c2, c3, c4, c5 = st.columns([2, 1, 0.7, 0.9, 1.5])
                                c1.write(f"*{ex.produto}*")
                                c2.write(formatar_para_br(ex.preco))

                                extra_id = int(ex.id)
                                qe = c3.number_input(
                                    "Qtd",
                                    min_value=0,
                                    step=1,
                                    key=f"qe_{id_f}_{extra_id}",
                                    label_visibility="collapsed",
                                )
                                ue = c4.selectbox(
                                    "Un",
                                    UNIDADES_PEDIDO,
                                    key=f"ue_{id_f}_{extra_id}",
                                    label_visibility="collapsed",
                                )
                                oe = c5.text_input(
                                    "Obs",
                                    key=f"oe_{id_f}_{extra_id}",
                                    label_visibility="collapsed",
                                )

                                linhas_pdf_conferencia.append(
                                    f"• [  ] - {ex.produto} (EXTRA) - {formatar_para_br(ex.preco)}"
                                )

                                if qe > 0:
                                    texto_extra = (
                                        f"• {qe} {ue} - {ex.produto} "
                                        f"{f'({oe})' if oe else ''} - {formatar_para_br(ex.preco)} (EXTRA)"
                                    )
                                    linhas.append(texto_extra)

                        # ITENS ADICIONADOS MANUALMENTE PELA ABA CONSULTAR ITEM
                        pedidos_manuais = get_pedidos_manuais()
                        itens_manuais_fornecedor = pedidos_manuais.get(str(id_f), [])

                        if itens_manuais_fornecedor:
                            st.markdown("---")
                            st.markdown("**Itens adicionados manualmente pela aba Consultar Item:**")

                            for idx_manual, item_manual in enumerate(list(itens_manuais_fornecedor)):
                                cm1, cm2 = st.columns([5, 1])
                                texto_manual = montar_texto_item_manual(item_manual)
                                cm1.write(texto_manual)
                                if cm2.button(
                                    "Remover",
                                    key=f"rem_manual_{id_f}_{idx_manual}_{item_manual.get('cotacao_id', 'semid')}",
                                ):
                                    remover_item_pedido_manual(id_f, idx_manual)
                                    st.rerun()

                                linhas.append(texto_manual)
                                linhas_pdf_conferencia.append(texto_manual)

                            if st.button("Limpar itens manuais deste fornecedor", key=f"limpar_manual_{id_f}"):
                                limpar_pedido_manual_fornecedor(id_f)
                                st.rerun()

                        st.divider()
                        col_pdf, col_zap = st.columns(2)

                        zap_msg = f"*PEDIDO BIG BERG 2 (CPV VELHA) - {forn}*\n\n"
                        zap_msg += "\n".join(linhas) if linhas else "Nenhum item com quantidade informada."

                        with col_pdf:
                            lista_para_o_pdf = linhas if linhas else linhas_pdf_conferencia
                            st.download_button(
                                "📄 Gerar Espelho PDF",
                                data=gerar_pdf_final(forn, lista_para_o_pdf),
                                file_name=f"pedido_{forn}.pdf",
                                key=f"pdf_{id_f}",
                            )

                        with col_zap:
                            st.markdown(
                                f"[📲 Enviar pelo WhatsApp](https://wa.me/?text={urllib.parse.quote(zap_msg)})"
                            )

                        st.code(zap_msg)

            st.divider()
            render_botao_encerrar_cotacao("ranking")

        # -------------------------------------------------
        # TAB 2: CONSULTAR ITEM
        # -------------------------------------------------
        with tab2:
            st.subheader("🔍 Consultar Opções por Item")
            st.caption(
                "Aqui você consulta todos os preços de um produto e pode adicionar uma opção específica ao pedido do fornecedor."
            )

            df_p_cota = conn.query(
                """
                SELECT DISTINCT p.id, p.nome
                FROM produtos p
                JOIN cotacoes c ON p.id = c.produto_id
                WHERE p.em_cotacao = TRUE
                ORDER BY p.nome
                """,
                ttl=0,
            )

            if df_p_cota.empty:
                st.info("Ainda não há produtos cotados para consultar.")
            else:
                item_busca = st.selectbox(
                    "Selecione o produto:",
                    ["---"] + [r.nome for r in df_p_cota.itertuples()],
                )

                if item_busca != "---":
                    q_todos = """
                        SELECT
                            c.id AS cotacao_id,
                            c.produto_id,
                            c.fornecedor_id,
                            f.empresa,
                            f.vendedor,
                            c.preco,
                            COALESCE(c.marca, '') AS marca,
                            f.whatsapp,
                            p.nome AS produto
                        FROM cotacoes c
                        JOIN fornecedores f ON c.fornecedor_id = f.id
                        JOIN produtos p ON c.produto_id = p.id
                        WHERE p.nome = :nome
                          AND p.em_cotacao = TRUE
                        ORDER BY c.preco ASC, f.empresa ASC
                    """
                    res_c = conn.query(q_todos, params={"nome": item_busca}, ttl=0)

                    if res_c.empty:
                        st.info("Nenhum preço encontrado para este produto.")
                    else:
                        st.markdown("### Opções encontradas")

                    for i, res in enumerate(res_c.itertuples()):
                        cor = "green" if i == 0 else "#2c3e50"
                        st.markdown(
                            f"""
                            <div style="border: 1px solid #ddd; padding: 15px; border-radius: 10px; margin-bottom: 10px; border-left: 10px solid {cor};">
                                <strong style="font-size: 1.1em;">{res.empresa}</strong> | Preço: <b style="color: #d35400;">{formatar_para_br(res.preco)}</b><br>
                                <small>Vendedor: {res.vendedor} | Marca: {res.marca if res.marca else 'N/A'}</small>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

                        col_qtd, col_un, col_obs, col_add, col_zap = st.columns([0.8, 1, 2, 2, 1])

                        qtd_add = col_qtd.number_input(
                            "Qtd",
                            min_value=1,
                            step=1,
                            value=1,
                            key=f"consulta_qtd_{int(res.cotacao_id)}",
                        )
                        un_add = col_un.selectbox(
                            "Un",
                            UNIDADES_PEDIDO,
                            key=f"consulta_un_{int(res.cotacao_id)}",
                        )
                        obs_add = col_obs.text_input(
                            "Obs",
                            key=f"consulta_obs_{int(res.cotacao_id)}",
                            placeholder="Opcional",
                        )

                        if col_add.button(
                            f"➕ Adicionar em pedido de {res.empresa}",
                            key=f"consulta_add_{int(res.cotacao_id)}",
                        ):
                            atualizado = adicionar_item_pedido_manual(
                                fornecedor_id=int(res.fornecedor_id),
                                empresa=res.empresa,
                                produto_id=int(res.produto_id),
                                produto=res.produto,
                                preco=float(res.preco),
                                marca=res.marca,
                                quantidade=int(qtd_add),
                                unidade=un_add,
                                observacao=obs_add,
                                cotacao_id=int(res.cotacao_id),
                            )
                            if atualizado:
                                st.success(f"Item atualizado no pedido de {res.empresa}.")
                            else:
                                st.success(f"Item adicionado ao pedido de {res.empresa}.")

                        if col_zap.button("📲 Zap", key=f"consulta_zap_{int(res.cotacao_id)}"):
                            msg = urllib.parse.quote(
                                f"Olá {res.vendedor}, gostaria de fechar o item *{item_busca}* por {formatar_para_br(res.preco)}."
                            )
                            whatsapp = "" if pd.isna(res.whatsapp) else str(res.whatsapp)
                            st.markdown(
                                f'<meta http-equiv="refresh" content="0;URL=https://wa.me/{whatsapp}?text={msg}">',
                                unsafe_allow_html=True,
                            )

                        st.divider()

                pedidos_manuais = get_pedidos_manuais()
                total_itens_manuais = sum(len(v) for v in pedidos_manuais.values())
                if total_itens_manuais > 0:
                    st.info(
                        f"Você tem {total_itens_manuais} item(ns) adicionado(s) manualmente. "
                        "Abra a aba Ranking para gerar o espelho/PDF/WhatsApp com eles."
                    )

        # -------------------------------------------------
        # TAB 3: EXTRAS
        # -------------------------------------------------
        with tab3:
            st.subheader("🔥 Visão Geral de Ofertas Extras")

            df_todas_ex = conn.query(
                """
                SELECT
                    o.id,
                    f.empresa,
                    f.vendedor,
                    o.produto,
                    o.preco,
                    f.whatsapp
                FROM ofertas_extras o
                JOIN fornecedores f ON o.fornecedor_id = f.id
                ORDER BY o.produto ASC, f.empresa ASC
                """,
                ttl=0,
            )

            if not df_todas_ex.empty:
                st.dataframe(df_todas_ex, use_container_width=True, hide_index=True)
            else:
                st.info("Nenhuma oferta extra foi enviada pelos fornecedores ainda.")

        # -------------------------------------------------
        # TAB 4: HISTÓRICO
        # -------------------------------------------------
        with tab4:
            st.subheader("📈 Histórico")
            try:
                h = conn.query("SELECT * FROM historico_precos ORDER BY data_compra DESC", ttl=0)
                st.dataframe(h, use_container_width=True, hide_index=True)
            except Exception as e:
                st.info(f"Não foi possível carregar o histórico: {e}")

        # -------------------------------------------------
        # TAB 5: GESTÃO
        # -------------------------------------------------
        with tab5:
            st.subheader("📦 Gestão da Cotação")

            df_total = conn.query(
                """
                SELECT
                    COUNT(*) FILTER (WHERE em_cotacao = TRUE) AS em_cotacao,
                    COUNT(*) AS total_produtos
                FROM produtos
                """,
                ttl=0,
            )

            total_em_cotacao = int(df_total.iloc[0]["em_cotacao"])
            total_produtos = int(df_total.iloc[0]["total_produtos"])

            m1, m2 = st.columns(2)
            m1.metric("Produtos em cotação", total_em_cotacao)
            m2.metric("Produtos cadastrados", total_produtos)

            st.divider()
            st.markdown("### ➕ Cadastrar / adicionar produtos na cotação")
            st.caption(
                "Cole uma lista com um produto por linha. O sistema cadastra o que não existir "
                "e coloca todos da lista como em_cotacao = TRUE."
            )

            with st.form("form_lista_produtos"):
                lista_produtos = st.text_area(
                    "Lista de produtos:",
                    height=300,
                    placeholder="CAFÉ PILÃO 500G\nDETERGENTE YPÊ\nBATATA PALHA 100G +BARATO",
                )

                limpar_antes = st.checkbox(
                    "Antes de adicionar esta lista, tirar todos os produtos atuais da cotação",
                    value=False,
                )

                enviar_lista = st.form_submit_button("✅ CADASTRAR / ADICIONAR NA COTAÇÃO")

                if enviar_lista:
                    produtos = normalizar_lista_produtos(lista_produtos)

                    if not produtos:
                        st.warning("Cole pelo menos um produto.")
                    else:
                        inseridos, atualizados = ativar_ou_cadastrar_produtos(
                            produtos,
                            limpar_antes=limpar_antes,
                        )

                        st.success(
                            f"Pronto! {len(produtos)} produto(s) processado(s). "
                            f"{atualizados} já existiam e foram ativados. "
                            f"{inseridos} foram cadastrados e ativados."
                        )
                        st.rerun()

            st.divider()
            st.markdown("### 🚫 Tirar produtos da cotação")
            st.caption(
                "Esta opção apenas coloca todos os produtos como em_cotacao = FALSE. "
                "Ela não apaga preços já enviados."
            )

            confirmar_limpeza = st.checkbox(
                "Confirmo que quero tirar todos os produtos da cotação",
                key="confirmar_limpeza_produtos",
            )

            if st.button("🚫 TIRAR TODOS OS PRODUTOS DA COTAÇÃO"):
                if not confirmar_limpeza:
                    st.warning("Marque a confirmação antes de limpar.")
                else:
                    tirar_todos_produtos_da_cotacao()
                    st.success("Todos os produtos foram removidos da cotação.")
                    st.rerun()

            st.divider()
            render_botao_encerrar_cotacao("gestao")

            st.divider()
            st.markdown("### 🔎 Ver produtos em cotação")
            if st.button("Atualizar visualização", key="atualizar_visao_produtos"):
                st.rerun()

            df_g = conn.query(
                "SELECT id, nome, em_cotacao FROM produtos WHERE em_cotacao = TRUE ORDER BY nome",
                ttl=0,
            )

            if df_g.empty:
                st.info("Nenhum produto está em cotação agora.")
            else:
                st.dataframe(df_g, use_container_width=True, hide_index=True)

        # -------------------------------------------------
        # TAB 6: MONITORAMENTO
        # -------------------------------------------------
        with tab6:
            st.subheader("👀 Monitoramento")

            col_a, col_b, col_c = st.columns(3)

            try:
                total_fornecedores = conn.query(
                    "SELECT COUNT(*) AS total FROM fornecedores",
                    ttl=30,
                ).iloc[0]["total"]

                fornecedores_responderam = conn.query(
                    "SELECT COUNT(DISTINCT fornecedor_id) AS total FROM cotacoes",
                    ttl=0,
                ).iloc[0]["total"]

                total_cotacoes = conn.query(
                    "SELECT COUNT(*) AS total FROM cotacoes",
                    ttl=0,
                ).iloc[0]["total"]

                col_a.metric("Fornecedores cadastrados", int(total_fornecedores))
                col_b.metric("Fornecedores que responderam", int(fornecedores_responderam))
                col_c.metric("Preços enviados", int(total_cotacoes))
            except Exception:
                st.info("Não foi possível carregar os indicadores principais.")

            st.divider()
            st.markdown("### Último envio por fornecedor")
            try:
                df_m = conn.query(
                    """
                    SELECT
                        f.empresa,
                        f.vendedor,
                        MAX(c.data_cadastro) AS ultimo_envio
                    FROM fornecedores f
                    JOIN cotacoes c ON f.id = c.fornecedor_id
                    GROUP BY f.empresa, f.vendedor
                    ORDER BY ultimo_envio DESC
                    """,
                    ttl=0,
                )
                st.dataframe(df_m, use_container_width=True, hide_index=True)
            except Exception as e:
                st.info(f"Sem dados de monitoramento: {e}")

            st.divider()
            st.markdown("### Produtos ativos sem nenhuma cotação")
            try:
                df_sem = conn.query(
                    """
                    SELECT p.id, p.nome
                    FROM produtos p
                    LEFT JOIN cotacoes c ON c.produto_id = p.id
                    WHERE p.em_cotacao = TRUE
                    GROUP BY p.id, p.nome
                    HAVING COUNT(c.id) = 0
                    ORDER BY p.nome
                    """,
                    ttl=0,
                )

                if df_sem.empty:
                    st.success("Todos os produtos ativos já receberam pelo menos uma cotação.")
                else:
                    st.dataframe(df_sem, use_container_width=True, hide_index=True)
            except Exception as e:
                st.info(f"Não foi possível verificar produtos sem cotação: {e}")

            st.divider()
            st.markdown("### Mesmo fornecedor com mais de um envio no mesmo produto")
            try:
                df_dup = conn.query(
                    """
                    SELECT
                        f.empresa,
                        f.vendedor,
                        p.nome AS produto,
                        COUNT(*) AS quantidade_envios,
                        COUNT(DISTINCT c.preco) AS precos_diferentes,
                        ARRAY_AGG(c.preco ORDER BY c.data_cotacao DESC) AS precos_enviados,
                        MIN(c.preco) AS menor_preco,
                        MAX(c.preco) AS maior_preco
                    FROM cotacoes c
                    JOIN fornecedores f ON f.id = c.fornecedor_id
                    JOIN produtos p ON p.id = c.produto_id
                    GROUP BY f.empresa, f.vendedor, p.nome, c.fornecedor_id, c.produto_id
                    HAVING COUNT(*) > 1
                    ORDER BY quantidade_envios DESC, f.empresa, p.nome
                    """,
                    ttl=0,
                )

                if df_dup.empty:
                    st.success("Nenhum fornecedor enviou mais de um preço para o mesmo produto.")
                else:
                    st.dataframe(df_dup, use_container_width=True, hide_index=True)
            except Exception as e:
                st.info(f"Não foi possível verificar duplicidades: {e}")
