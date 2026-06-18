from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json
import os

app = Flask(__name__)

# Configurar PostgreSQL a partir da variável de ambiente
# O Vercel irá definir esta variável automaticamente ou pode configurar manualmente
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', '').replace('postgres://', 'postgresql://')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-para-teste')

db = SQLAlchemy(app)

# ==================== MODELOS ====================

class Produto(db.Model):
    __tablename__ = 'produtos'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    preco = db.Column(db.Float, nullable=False)

class PedidoAtivo(db.Model):
    __tablename__ = 'pedidos_ativos'
    id = db.Column(db.Integer, primary_key=True)
    produto_id = db.Column(db.Integer, db.ForeignKey('produtos.id'))
    quantidade = db.Column(db.Integer, nullable=False)
    data_hora = db.Column(db.DateTime, default=datetime.utcnow)

class PedidoGravado(db.Model):
    __tablename__ = 'pedidos_gravados'
    id = db.Column(db.Integer, primary_key=True)
    pedido_json = db.Column(db.Text, nullable=False)
    total = db.Column(db.Float, nullable=False)
    entregue = db.Column(db.Integer, default=0)
    data_hora = db.Column(db.DateTime, default=datetime.utcnow)

class Config(db.Model):
    __tablename__ = 'config'
    chave = db.Column(db.String(50), primary_key=True)
    valor = db.Column(db.String(255), nullable=False)

# ==================== FUNÇÕES AUXILIARES ====================

def init_db():
    """Inicializa a base de dados com dados padrão"""
    with app.app_context():
        db.create_all()
        
        # Inserir próximo ID do pedido se não existir
        if not Config.query.filter_by(chave='proximo_pedido_id').first():
            config = Config(chave='proximo_pedido_id', valor='1')
            db.session.add(config)
        
        # Inserir produtos padrão se não existirem
        if Produto.query.count() == 0:
            produtos_padrao = [

				Produto(nome='Água', preco=0.50),
                Produto(nome='Água com Gás', preco=1.20),                
                Produto(nome='Café', preco=0.50),
                Produto(nome='7-UP', preco=1.50),
                Produto(nome='Ice Tea', preco=1.50),
                Produto(nome='Coca-Cola', preco=1.50),
                Produto(nome='Cerveja Mini', preco=1.20),
                Produto(nome='Vinho ao Copo', preco=0.80), 
                Produto(nome='Sangria', preco=1.50), 
                Produto(nome='Fatia de Bolo', preco=1.00),                
                Produto(nome='Caldo Verde', preco=2.00),
                Produto(nome='Fêveras no Pão', preco=2.50),
                Produto(nome='Rojões no Pão', preco=1.50),
                Produto(nome='Pão com Chouriço', preco=1.50),
                Produto(nome='Cachorro', preco=2.00),     
                Produto(nome='Pizza Produto(nome=fatia)', preco=1.50),
                Produto(nome='Bola Produto(nome=fatia)', preco=1.50),
                Produto(nome='Dobradinha', preco=2.50),
                Produto(nome='Moelas', preco=2.00),
                Produto(nome='Rojões das Tripas Produto(nome=unidade)', preco=0.50),                
                Produto(nome='Batata Frita Produto(nome=prato)', preco=0.80),
                Produto(nome='Azeitonas', preco=0.50),
                Produto(nome='Tremoços', preco=0.50),
                Produto(nome='Amendoins', preco=0.50) 
            ]
            db.session.add_all(produtos_padrao)
        
        db.session.commit()

def get_proximo_pedido_id():
    config = Config.query.filter_by(chave='proximo_pedido_id').first()
    return int(config.valor) if config else 1

def incrementar_proximo_pedido_id():
    config = Config.query.filter_by(chave='proximo_pedido_id').first()
    if config:
        config.valor = str(int(config.valor) + 1)
        db.session.commit()

# ==================== ROTAS ====================

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
    produtos = Produto.query.order_by(Produto.id).all()
    return jsonify([{'id': p.id, 'nome': p.nome, 'preco': p.preco} for p in produtos])

@app.route('/api/produto', methods=['POST'])
def adicionar_produto():
    data = request.json
    nome = data.get('nome')
    preco = data.get('preco')
    
    if not nome or preco is None:
        return jsonify({'error': 'Nome e preço são obrigatórios'}), 400
    
    novo_produto = Produto(nome=nome, preco=preco)
    db.session.add(novo_produto)
    db.session.commit()
    
    return jsonify({'success': True, 'id': novo_produto.id})

@app.route('/api/produto/<int:produto_id>', methods=['PUT'])
def atualizar_produto(produto_id):
    data = request.json
    produto = Produto.query.get(produto_id)
    
    if not produto:
        return jsonify({'error': 'Produto não encontrado'}), 404
    
    produto.nome = data.get('nome')
    produto.preco = data.get('preco')
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/api/produto/<int:produto_id>', methods=['DELETE'])
def deletar_produto(produto_id):
    produto = Produto.query.get(produto_id)
    
    if not produto:
        return jsonify({'error': 'Produto não encontrado'}), 404
    
    db.session.delete(produto)
    # Remover referências nos pedidos ativos
    PedidoAtivo.query.filter_by(produto_id=produto_id).delete()
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/api/pedido', methods=['POST'])
def salvar_pedido():
    data = request.json
    produto_id = data.get('produto_id')
    quantidade = data.get('quantidade')
    
    pedido = PedidoAtivo.query.filter_by(produto_id=produto_id).first()
    
    if pedido:
        if quantidade == 0:
            db.session.delete(pedido)
        else:
            pedido.quantidade = quantidade
    else:
        if quantidade > 0:
            novo_pedido = PedidoAtivo(produto_id=produto_id, quantidade=quantidade)
            db.session.add(novo_pedido)
    
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/pedidos', methods=['GET'])
def get_pedidos():
    produtos = Produto.query.all()
    pedidos = {p.produto_id: p.quantidade for p in PedidoAtivo.query.all()}
    
    return jsonify([{
        'id': p.id,
        'nome': p.nome,
        'preco': p.preco,
        'quantidade': pedidos.get(p.id, 0)
    } for p in produtos])

@app.route('/api/gravar_pedido', methods=['POST'])
def gravar_pedido():
    try:
        data = request.json
        itens = data.get('itens', [])
        total = data.get('total', 0)
        pedido_id = get_proximo_pedido_id()
        
        pedido = PedidoGravado(
            id=pedido_id,
            pedido_json=json.dumps(itens),
            total=total,
            entregue=0
        )
        db.session.add(pedido)
        
        # Limpar pedidos ativos
        PedidoAtivo.query.delete()
        
        db.session.commit()
        incrementar_proximo_pedido_id()
        
        return jsonify({'success': True, 'pedido_id': pedido_id})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/cancelar_pedido', methods=['POST'])
def cancelar_pedido():
    PedidoAtivo.query.delete()
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/historico', methods=['GET'])
def get_historico():
    pedidos = PedidoGravado.query.order_by(PedidoGravado.data_hora.desc()).all()
    
    historico = []
    for p in pedidos:
        historico.append({
            'id': p.id,
            'itens': json.loads(p.pedido_json),
            'total': p.total,
            'entregue': bool(p.entregue),
            'data_hora': p.data_hora.isoformat()
        })
    
    return jsonify(historico)

@app.route('/api/marcar_entregue/<int:pedido_id>', methods=['PUT'])
def marcar_entregue(pedido_id):
    pedido = PedidoGravado.query.get(pedido_id)
    if not pedido:
        return jsonify({'error': 'Pedido não encontrado'}), 404
    
    pedido.entregue = 1
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/marcar_nao_entregue/<int:pedido_id>', methods=['PUT'])
def marcar_nao_entregue(pedido_id):
    pedido = PedidoGravado.query.get(pedido_id)
    if not pedido:
        return jsonify({'error': 'Pedido não encontrado'}), 404
    
    pedido.entregue = 0
    db.session.commit()
    return jsonify({'success': True})

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
