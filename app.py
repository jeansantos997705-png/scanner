from flask import Flask, render_template, request, jsonify
import sqlite3
from datetime import datetime
import os

app = Flask(__name__)
DATABASE = os.path.join(app.root_path, 'estoque.db')


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Produtos (
            id INTEGER PRIMARY KEY,
            codigo_barra TEXT UNIQUE NOT NULL,
            nome TEXT NOT NULL,
            estoque_atual INTEGER NOT NULL DEFAULT 0
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Historico_Contagem (
            id INTEGER PRIMARY KEY,
            produto_id INTEGER,
            codigo_barra_lido TEXT NOT NULL,
            quantidade INTEGER NOT NULL,
            data_hora TEXT NOT NULL,
            FOREIGN KEY(produto_id) REFERENCES Produtos(id)
        )
    ''')

    conn.commit()
    conn.close()


with app.app_context():
    init_db()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/escanear', methods=['POST'])
def escanear_codigo():
    data = request.get_json()
    codigo_barra = data.get('codigo_barra')

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('SELECT id, nome FROM Produtos WHERE codigo_barra = ?', (codigo_barra,))
    produto = cursor.fetchone()
    conn.close()

    if produto:
        return jsonify({
            'success': True,
            'message': f'Produto encontrado: {produto["nome"]}',
            'codigo_barra': codigo_barra,
            'nome': produto['nome']
        })
    else:
        return jsonify({
            'success': False,
            'message': 'Produto não cadastrado.',
            'codigo_barra': codigo_barra,
        })


@app.route('/api/cadastrar_produto', methods=['POST'])
def cadastrar_produto():
    data = request.get_json()
    codigo_barra = data.get('codigo_barra')
    nome = data.get('nome')

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO Produtos (codigo_barra, nome, estoque_atual)
            VALUES (?, ?, 0)
        ''', (codigo_barra, nome))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': f'Produto "{nome}" cadastrado com sucesso.'})
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'success': False, 'message': 'Erro: Código de barras já existe no banco de dados.'})


@app.route('/api/salvar_contagem', methods=['POST'])
def salvar_contagem():
    contagem_sessao = request.get_json()

    conn = get_db()
    cursor = conn.cursor()
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    try:
        for codigo_barra, item_data in contagem_sessao.items():
            quantidade = item_data['quantidade']

            cursor.execute('SELECT id, estoque_atual FROM Produtos WHERE codigo_barra = ?', (codigo_barra,))
            produto = cursor.fetchone()

            if produto:
                produto_id = produto['id']
                novo_estoque = produto['estoque_atual'] + quantidade

                cursor.execute('UPDATE Produtos SET estoque_atual = ? WHERE id = ?', (novo_estoque, produto_id))

                cursor.execute('''
                    INSERT INTO Historico_Contagem (produto_id, codigo_barra_lido, quantidade, data_hora)
                    VALUES (?, ?, ?, ?)
                ''', (produto_id, codigo_barra, quantidade, timestamp))

        conn.commit()
        return jsonify({'success': True, 'message': 'Contagem salva e estoque atualizado com sucesso!'})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Erro ao salvar contagem: {str(e)}'})
    finally:
        conn.close()


@app.route('/api/dados_completos', methods=['GET'])
def get_dados_completos():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT codigo_barra, nome, estoque_atual FROM Produtos')
    produtos = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(produtos)


if __name__ == '__main__':
    app.run(debug=True)
