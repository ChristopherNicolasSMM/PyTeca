import os

if os.getenv('FLASK_ENV') == 'DEV':
    from db.dev_database import init_db , db, test_connection 
    pass 
elif os.getenv('FLASK_ENV') == 'PRD' or os.getenv('FLASK_ENV') == 'Production':        
    from db.prd_database import init_db , db, test_connection 
    pass 
else:
    raise Exception("FLASK_ENV não definido ou valor inválido. Use 'DEV' para desenvolvimento ou 'PRD' para produção.")
    