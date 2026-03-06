#include <QApplication>
#include <iostream>

#include "App/AppController.h"

int main(int argc, char* argv[])
{
    QApplication app(argc, argv);

    AppController controller;
    const bool ok = controller.initialize();

    if (!ok)
    {
        std::cerr << "Falha no teste de inicialização do FBNeo." << std::endl;
        return 1;
    }

    std::cout << "Teste de inicialização concluído com sucesso." << std::endl;
    return 0;
}
