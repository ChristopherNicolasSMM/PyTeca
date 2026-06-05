# routes/upload_routes.py

from flask import Blueprint

upload_bp = Blueprint("upload", __name__)

# @upload_bp.route('/upload/maltes', methods=['POST'])
# @login_required
# def upload_maltes():
#    """Upload de planilha de maltes"""
#    if 'file' not in request.files:
#        return jsonify({'error': 'Nenhum arquivo enviado'}), 400
#
#    file = request.files['file']
#    if file.filename == '':
#        return jsonify({'error': 'Nenhum arquivo selecionado'}), 400
#
#    try:
#        # Ler arquivo Excel
#        df = pd.read_excel(file)
#
#        # Validar colunas
#        required_columns = ['Nome', 'Fabricante', 'Cor_EBC', 'Poder_Diastatico', 'Rendimento', 'Preco_Kg', 'Tipo']
#        if not all(col in df.columns for col in required_columns):
#            return jsonify({'error': f'Colunas obrigatórias: {required_columns}'}), 400
#
#        # Processar dados
#        maltes_criados = 0
#        for _, row in df.iterrows():
#            malte = Malte(
#                nome=row['Nome'],
#                fabricante=row['Fabricante'],
#                cor_ebc=float(row['Cor_EBC']),
#                poder_diastatico=float(row['Poder_Diastatico']),
#                rendimento=float(row['Rendimento']),
#                preco_kg=float(row['Preco_Kg']),
#                tipo=row['Tipo']
#            )
#            db.session.add(malte)
#            maltes_criados += 1
#
#        db.session.commit()
#
#        return jsonify({
#            'message': f'{maltes_criados} maltes importados com sucesso',
#            'quantidade': maltes_criados
#        }), 200
#
#    except Exception as e:
#        return jsonify({'error': f'Erro ao processar arquivo: {str(e)}'}), 400
#
# @upload_bp.route('/upload/modelo/<tipo>', methods=['GET'])
# @login_required
# def download_modelo(tipo):
#    """Download do modelo de planilha para importação"""
#    try:
#        if tipo == 'maltes':
#            # Criar DataFrame modelo para maltes
#            df = pd.DataFrame(columns=[
#                'Nome', 'Fabricante', 'Cor_EBC', 'Poder_Diastatico',
#                'Rendimento', 'Preco_Kg', 'Tipo'
#            ])
#            # Adicionar exemplo
#            df.loc[0] = [
#                'Pilsen', 'Weyermann', 3.5, 120, 80.5, 15.90, 'Base'
#            ]
#
#        elif tipo == 'lupulos':
#            # Criar DataFrame modelo para lúpulos
#            df = pd.DataFrame(columns=[
#                'Nome', 'Fabricante', 'Alpha_Acidos', 'Beta_Acidos',
#                'Formato', 'Origem', 'Preco_Kg', 'Aroma'
#            ])
#            # Adicionar exemplo
#            df.loc[0] = [
#                'Cascade', 'EUA', 5.5, 7.2, 'Pellet', 'Estados Unidos', 280.00, 'Cítrico, Floral'
#            ]
#
#        elif tipo == 'leveduras':
#            # Criar DataFrame modelo para leveduras
#            df = pd.DataFrame(columns=[
#                'Nome', 'Fabricante', 'Formato', 'Atenuacao',
#                'Temp_Fermentacao', 'Preco_Unidade', 'Floculacao'
#            ])
#            # Adicionar exemplo
#            df.loc[0] = [
#                'US-05', 'Fermentis', 'Seca', 78, 18.0, 12.50, 'Média'
#            ]
#
#        else:
#            return jsonify({'error': 'Tipo de ingrediente inválido'}), 400
#
#        # Criar arquivo em memória
#        output = io.BytesIO()
#        with pd.ExcelWriter(output, engine='openpyxl') as writer:
#            df.to_excel(writer, sheet_name=f'Modelo_{tipo}', index=False)
#
#            # Ajustar largura das colunas
#            worksheet = writer.sheets[f'Modelo_{tipo}']
#            for column in worksheet.columns:
#                max_length = 0
#                column_letter = column[0].column_letter
#                for cell in column:
#                    try:
#                        if len(str(cell.value)) > max_length:
#                            max_length = len(str(cell.value))
#                    except:
#                        pass
#                adjusted_width = min(max_length + 2, 30)
#                worksheet.column_dimensions[column_letter].width = adjusted_width
#
#        output.seek(0)
#
#        return send_file(
#            output,
#            as_attachment=True,
#            download_name=f'modelo_{tipo}.xlsx',
#            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
#        )
#
#    except Exception as e:
#        return jsonify({'error': f'Erro ao gerar modelo: {str(e)}'}), 500
#
# @upload_bp.route('/upload/exportar/<tipo>', methods=['GET'])
# @login_required
# def exportar_ingredientes(tipo):
#    """Exportar ingredientes para Excel"""
#    try:
#        if tipo == 'maltes':
#            ingredientes = Malte.query.filter_by(ativo=True).all()
#            data = [{
#                'Nome': m.nome,
#                'Fabricante': m.fabricante,
#                'Cor_EBC': m.cor_ebc,
#                'Poder_Diastatico': m.poder_diastatico,
#                'Rendimento': m.rendimento,
#                'Preco_Kg': m.preco_kg,
#                'Tipo': m.tipo,
#                'Data_Criacao': m.data_criacao.strftime('%d/%m/%Y %H:%M') if m.data_criacao else ''
#            } for m in ingredientes]
#            df = pd.DataFrame(data)
#
#        elif tipo == 'lupulos':
#            ingredientes = Lupulo.query.filter_by(ativo=True).all()
#            data = [{
#                'Nome': l.nome,
#                'Fabricante': l.fabricante,
#                'Alpha_Acidos': l.alpha_acidos,
#                'Beta_Acidos': l.beta_acidos,
#                'Formato': l.formato,
#                'Origem': l.origem,
#                'Preco_Kg': l.preco_kg,
#                'Aroma': l.aroma,
#                'Data_Criacao': l.data_criacao.strftime('%d/%m/%Y %H:%M') if l.data_criacao else ''
#            } for l in ingredientes]
#            df = pd.DataFrame(data)
#
#        elif tipo == 'leveduras':
#            ingredientes = Levedura.query.filter_by(ativo=True).all()
#            data = [{
#                'Nome': l.nome,
#                'Fabricante': l.fabricante,
#                'Formato': l.formato,
#                'Atenuacao': l.atenuacao,
#                'Temp_Fermentacao': l.temp_fermentacao,
#                'Preco_Unidade': l.preco_unidade,
#                'Floculacao': l.floculacao,
#                'Data_Criacao': l.data_criacao.strftime('%d/%m/%Y %H:%M') if l.data_criacao else ''
#            } for l in ingredientes]
#            df = pd.DataFrame(data)
#
#        else:
#            return jsonify({'error': 'Tipo de ingrediente inválido'}), 400
#
#        # Criar arquivo em memória
#        output = io.BytesIO()
#        with pd.ExcelWriter(output, engine='openpyxl') as writer:
#            df.to_excel(writer, sheet_name=f'{tipo.capitalize()}', index=False)
#
#            # Ajustar largura das colunas
#            worksheet = writer.sheets[f'{tipo.capitalize()}']
#            for column in worksheet.columns:
#                max_length = 0
#                column_letter = column[0].column_letter
#                for cell in column:
#                    try:
#                        if len(str(cell.value)) > max_length:
#                            max_length = len(str(cell.value))
#                    except:
#                        pass
#                adjusted_width = min(max_length + 2, 30)
#                worksheet.column_dimensions[column_letter].width = adjusted_width
#
#        output.seek(0)
#
#        return send_file(
#            output,
#            as_attachment=True,
#            download_name=f'{tipo}_exportados_{datetime.now().strftime("%Y%m%d_%H%M")}.xlsx',
#            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
#        )
#
#    except Exception as e:
#        return jsonify({'error': f'Erro ao exportar dados: {str(e)}'}), 500
#
#
#
##
