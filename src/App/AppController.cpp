#include "AppController.h"

#include <iostream>
#include <tchar.h>

extern "C" {
#include "burn.h"
}

AppController::AppController()
{
}

bool AppController::initialize()
{
    std::cout << "Inicializando FBNeo..." << std::endl;

    if (BurnLibInit() != 0)
    {
        std::cout << "Falha ao inicializar BurnLib!" << std::endl;
        return false;
    }

    // Nesta API, use o contador global exportado.
    const int driverCount = nBurnDrvCount;

    std::cout << "FBNeo inicializado com sucesso!" << std::endl;
    std::cout << "Drivers disponíveis: " << driverCount << std::endl;

    BurnLibExit();
    return true;
}
