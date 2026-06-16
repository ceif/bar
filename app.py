from flask import Flask, render_template, request, jsonify
import sqlite3
from datetime import datetime
import json
import time
from contextlib import contextmanager

app = Flask(__name__)

# Context manager para gerenciar conexões com o banco de dados
@contextmanager
def get_db():
    """Gerencia a conexão com o banco de dados"""
    conn = None
    try:
        conn = sqlite3.connect('produtos.db', timeout=20)
        conn.row_factory = sqlite3.Row
        yield conn
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        raise e
    finally:
        if conn:
            conn.close()

def init_db():
    """Inicializa o banco de dados SQLite"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Tabela de produtos
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS produtos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                preco REAL NOT NULL
            )
        ''')
        
        # Tabela de pedidos ativos (carrinho atual)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pedidos_ativos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                produto_id INTEGER,
                quantidade INTEGER NOT NULL,
                data_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (produto_id) REFERENCES produtos (id)
            )
        ''')
        
        # Tabela de pedidos gravados (histórico) - com campo entregue
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pedidos_gravados (
                id INTEGER PRIMARY KEY,
                pedido_json TEXT NOT NULL,
                total REAL NOT NULL,
                entregue INTEGER DEFAULT 0,
                data_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tabela para controle do próximo ID do pedido
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS config (
                chave TEXT PRIMARY KEY,
                valor TEXT NOT NULL
            )
        ''')
        
        # Inserir próximo ID do pedido se não existir
        cursor.execute('SELECT COUNT(*) FROM config WHERE chave = "proximo_pedido_id"')
        if cursor.fetchone()[0] == 0:
            cursor.execute('INSERT INTO config (chave, valor) VALUES ("proximo_pedido_id", "1")')
        
        # Inserir produtos padrão se não existirem
        cursor.execute('SELECT COUNT(*) FROM produtos')
        if cursor.fetchone()[0] == 0:
            produtos_padrao = [
                ('Água', 0.50),
                ('Água com Gás', 1.20),                
                ('Café', 0.50),
                ('7-UP', 1.50),
                ('Ice Tea', 1.50),
                ('Coca-Cola', 1.50),
                ('Cerveja Mini', 1.20),
                ('Vinho ao Copo', 0.80), 
                ('Sangria', 1.50), 
                ('Fatia de Bolo', 1.00),                
                ('Caldo Verde', 2.00),
                ('Fêveras no Pão', 2.50),
                ('Rojões no Pão', 1.50),
                ('Pão com Chouriço', 1.50),
                ('Cachorro', 2.00),     
                ('Pizza (fatia)', 1.50),
                ('Bola (fatia)', 1.50),
                ('Dobradinha', 2.50),
                ('Moelas', 2.00),
                ('Rojões das Tripas (unidade)', 0.50),                
                ('Batata Frita (prato)', 0.80),
                ('Azeitonas', 0.50),
                ('Tremoços', 0.50),
                ('Amendoins', 0.50)              
            ]
            cursor.executemany('INSERT INTO produtos (nome, preco) VALUES (?, ?)', produtos_padrao)

def get_proximo_pedido_id():
    """Retorna o próximo ID do pedido"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT valor FROM config WHERE chave = "proximo_pedido_id"')
        resultado = cursor.fetchone()
        return int(resultado[0]) if resultado else 1

def incrementar_proximo_pedido_id():
    """Incrementa o próximo ID do pedido"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE config SET valor = CAST(valor AS INTEGER) + 1 WHERE chave = "proximo_pedido_id"')

@app.route('/')
def index():
    proximo_id = get_proximo_pedido_id()
    return render_template('index.html', proximo_pedido_id=proximo_id)

@app.route('/admin')
def admin():
    return render_template('admin.html')

@app.route('/historico')
def historico():
    return render_template('historico.html')

@app.route('/api/produtos', methods=['GET'])
def get_produtos():
    """Retorna todos os produtos"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT id, nome, preco FROM produtos ORDER BY id')
        produtos = cursor.fetchall()
        return jsonify([{'id': p[0], 'nome': p[1], 'preco': p[2]} for p in produtos])

@app.route('/api/produto', methods=['POST'])
def adicionar_produto():
    """Adiciona um novo produto"""
    data = request.json
    nome = data.get('nome')
    preco = data.get('preco')
    
    if not nome or preco is None:
        return jsonify({'error': 'Nome e preço são obrigatórios'}), 400
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('INSERT INTO produtos (nome, preco) VALUES (?, ?)', (nome, preco))
        novo_id = cursor.lastrowid
    
    return jsonify({'success': True, 'id': novo_id})

@app.route('/api/produto/<int:produto_id>', methods=['PUT'])
def atualizar_produto(produto_id):
    """Atualiza um produto existente"""
    data = request.json
    nome = data.get('nome')
    preco = data.get('preco')
    
    if not nome or preco is None:
        return jsonify({'error': 'Nome e preço são obrigatórios'}), 400
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE produtos SET nome = ?, preco = ? WHERE id = ?', (nome, preco, produto_id))
    
    return jsonify({'success': True})

@app.route('/api/produto/<int:produto_id>', methods=['DELETE'])
def deletar_produto(produto_id):
    """Remove um produto"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Verificar se o produto existe
        cursor.execute('SELECT id FROM produtos WHERE id = ?', (produto_id,))
        if not cursor.fetchone():
            return jsonify({'error': 'Produto não encontrado'}), 404
        
        # Remover produto
        cursor.execute('DELETE FROM produtos WHERE id = ?', (produto_id,))
        # Remover referências nos pedidos ativos
        cursor.execute('DELETE FROM pedidos_ativos WHERE produto_id = ?', (produto_id,))
    
    return jsonify({'success': True})

@app.route('/api/pedido', methods=['POST'])
def salvar_pedido():
    """Salva ou atualiza um pedido ativo"""
    data = request.json
    produto_id = data.get('produto_id')
    quantidade = data.get('quantidade')
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Verificar se já existe pedido para este produto
        cursor.execute('SELECT id, quantidade FROM pedidos_ativos WHERE produto_id = ?', (produto_id,))
        existente = cursor.fetchone()
        
        if existente:
            if quantidade == 0:
                # Remover se quantidade for zero
                cursor.execute('DELETE FROM pedidos_ativos WHERE produto_id = ?', (produto_id,))
            else:
                # Atualizar quantidade
                cursor.execute('UPDATE pedidos_ativos SET quantidade = ? WHERE produto_id = ?', 
                             (quantidade, produto_id))
        else:
            if quantidade > 0:
                # Inserir novo pedido
                cursor.execute('INSERT INTO pedidos_ativos (produto_id, quantidade) VALUES (?, ?)', 
                             (produto_id, quantidade))
    
    return jsonify({'success': True})

@app.route('/api/pedidos', methods=['GET'])
def get_pedidos():
    """Retorna todos os pedidos ativos"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT p.id, p.nome, p.preco, COALESCE(ped.quantidade, 0) as quantidade
            FROM produtos p
            LEFT JOIN pedidos_ativos ped ON p.id = ped.produto_id
            ORDER BY p.id
        ''')
        resultados = cursor.fetchall()
        
        return jsonify([{
            'id': r[0],
            'nome': r[1],
            'preco': r[2],
            'quantidade': r[3]
        } for r in resultados])

@app.route('/api/gravar_pedido', methods=['POST'])
def gravar_pedido():
    """Grava o pedido atual no histórico"""
    try:
        data = request.json
        itens = data.get('itens', [])
        total = data.get('total', 0)
        pedido_id = get_proximo_pedido_id()
        
        # Usar uma transação separada para gravar o pedido
        with get_db() as conn:
            cursor = conn.cursor()
            
            # Gravar pedido no histórico com o ID específico e entregue = 0 (não entregue)
            cursor.execute('''
                INSERT INTO pedidos_gravados (id, pedido_json, total, entregue)
                VALUES (?, ?, ?, ?)
            ''', (pedido_id, json.dumps(itens), total, 0))
            
            # Limpar pedidos ativos
            cursor.execute('DELETE FROM pedidos_ativos')
        
        # Incrementar próximo ID em uma transação separada
        incrementar_proximo_pedido_id()
        
        return jsonify({'success': True, 'pedido_id': pedido_id})
    
    except Exception as e:
        print(f"Erro ao gravar pedido: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/cancelar_pedido', methods=['POST'])
def cancelar_pedido():
    """Cancela o pedido atual (limpa o carrinho)"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM pedidos_ativos')
    
    return jsonify({'success': True})

@app.route('/api/historico', methods=['GET'])
def get_historico():
    """Retorna todos os pedidos gravados"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, pedido_json, total, entregue, data_hora 
            FROM pedidos_gravados 
            ORDER BY data_hora DESC
        ''')
        resultados = cursor.fetchall()
        
        historico = []
        for r in resultados:
            historico.append({
                'id': r[0],
                'itens': json.loads(r[1]),
                'total': r[2],
                'entregue': bool(r[3]),
                'data_hora': r[4]
            })
        
        return jsonify(historico)

@app.route('/api/marcar_entregue/<int:pedido_id>', methods=['PUT'])
def marcar_entregue(pedido_id):
    """Marca um pedido como entregue"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE pedidos_gravados SET entregue = 1 WHERE id = ?', (pedido_id,))
        
        if cursor.rowcount == 0:
            return jsonify({'error': 'Pedido não encontrado'}), 404
    
    return jsonify({'success': True})

@app.route('/api/marcar_nao_entregue/<int:pedido_id>', methods=['PUT'])
def marcar_nao_entregue(pedido_id):
    """Marca um pedido como não entregue"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE pedidos_gravados SET entregue = 0 WHERE id = ?', (pedido_id,))
        
        if cursor.rowcount == 0:
            return jsonify({'error': 'Pedido não encontrado'}), 404
    
    return jsonify({'success': True})

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
