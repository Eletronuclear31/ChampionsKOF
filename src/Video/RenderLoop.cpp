#include "RenderLoop.h"
#include "GameWindow.h"
#include "../Platform/HighPrecisionTimer.h"

#include <QMetaObject>
#include <windows.h>

static constexpr double TARGET_FRAME_MS = 1000.0 / 60.0;

RenderLoop::RenderLoop(GameWindow* window)
    : m_window(window)
{
}

void RenderLoop::stop()
{
    m_running = false;
}

void RenderLoop::run()
{
    HighPrecisionTimer timer;
    double accumulator = 0.0;

    while (m_running)
    {
        double elapsed = timer.elapsedMilliseconds();
        timer.reset();

        accumulator += elapsed;

        while (accumulator >= TARGET_FRAME_MS)
        {
            // Futuro:
            // core.runFrame();

            accumulator -= TARGET_FRAME_MS;
        }

        QMetaObject::invokeMethod(
            m_window,
            "update",
            Qt::QueuedConnection
            );

        Sleep(0);
    }
}
