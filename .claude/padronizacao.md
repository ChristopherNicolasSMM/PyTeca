# Padrões a ser implementado, estilo visual e comportamento.


## Listas
As listas devem por padrão ter rotas e funcionalidade já padronizadas para (filtros e pesquisa (sistema de filtro e pesquisa dinamicos), ordenação, re-posicionamento de campos, salvar layout (por usuário ou expor a todos os usuários), exportar dados para (excel, csv, pdf horizontal com cabeçalho), páginação se ira exibir a página por 10, 20, 50, 100. , botão para consulta de quantos registros tem )
Todas as listas devem contemplar este sistema.


## Model
Deverá ser possível por meio do Model e utilizando linha de comando, classes e scripts para gerar código por meio do model, fazer um crud completo com lista, detalhes, form com editar, inativar, atualizar, criar. Para isso será também criado os respectivos itens como controller, api/route, tests, registrado os bp, incluido criação de tabelas em db, tudo de forma automatica e seguindo exatamente o modelo que tenhamos pre definido, sendo possível configurar o mesmo.
Caso seja feito um segundo build tem de ter arquivo yaml controlando versionamento e realizar bkp do código antigo. 


## CRUD
O Crud deverá obedeser a base cadastrada como formulários e etc, e ao ser gerado não deverá apagar ou editar código customizado na folha, que tenha sido incluido pelo usuário desde que tenha um nome fora dos utilizados como padrão para o crud. 

## Area de query, deverá ter uma área onde é listado os objetos do db, sendo permitido realizar a consulta, seleção e modificação de dados, não se limitando também a joins mas buscas completas pelo DB por meio de interface python flask dentro do sistema. Esta área deverá utilizar como base a parte db/database e ficar dentro da pasta utils, podendo ser cambianda e acrescentada a outros sistemas com facilidade. 

## Área de ferramentas -> possível listar e chamar scripts e ter um console python em tempo de execução

## Criação de task e theads
A ser pensado e definido. 

