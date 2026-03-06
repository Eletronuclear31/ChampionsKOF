#include "CoreThread.h"
#include "ICore.h"

CoreThread::CoreThread(ICore* core)
    : m_core(core)
{
}

CoreThread::~CoreThread()
{
    stop();
    wait();
}

void CoreThread::requestFrame(uint32_t inputMask)
{
    QMutexLocker locker(&m_mutex);
    m_pendingInput = inputMask;
    m_frameRequested = true;
    m_frameCompleted = false;
    m_condition.wakeOne();
}

void CoreThread::waitForFrameComplete()
{
    while (!m_frameCompleted)
    {
        QThread::yieldCurrentThread();
    }
}

void CoreThread::stop()
{
    m_running = false;
    m_condition.wakeOne();
}

void CoreThread::run()
{
    if (!m_core)
        return;

    m_core->initialize();

    while (m_running)
    {
        m_mutex.lock();

        if (!m_frameRequested)
            m_condition.wait(&m_mutex);

        if (!m_running)
        {
            m_mutex.unlock();
            break;
        }

        uint32_t input = m_pendingInput;
        m_frameRequested = false;
        m_mutex.unlock();

        m_core->runFrame(input);

        m_frameCompleted = true;
    }
}
