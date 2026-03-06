#include "GameWindow.h"
#include <QCloseEvent>

GameWindow::GameWindow()
{
    setSurfaceType(QSurface::OpenGLSurface);
}

void GameWindow::initializeGL()
{
    initializeOpenGLFunctions();
    glClearColor(0.05f, 0.05f, 0.05f, 1.0f);
}

void GameWindow::resizeGL(int w, int h)
{
    glViewport(0, 0, w, h);
}

void GameWindow::paintGL()
{
    glClear(GL_COLOR_BUFFER_BIT);
}

void GameWindow::closeEvent(QCloseEvent* event)
{
    emit windowClosing();
    event->accept();
}
