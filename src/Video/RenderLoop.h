#pragma once

#include <QThread>
#include <atomic>

class GameWindow;

class RenderLoop : public QThread
{
public:
    RenderLoop(GameWindow* window);
    void stop();

protected:
    void run() override;

private:
    GameWindow* m_window;
    std::atomic<bool> m_running{ true };
};
