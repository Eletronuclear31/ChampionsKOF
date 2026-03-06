#pragma once

#include <QThread>
#include <QWaitCondition>
#include <QMutex>
#include <atomic>

class ICore;

class CoreThread : public QThread
{
    Q_OBJECT

public:
    explicit CoreThread(ICore* core);
    ~CoreThread();

    void requestFrame(uint32_t inputMask);
    void waitForFrameComplete();
    void stop();

protected:
    void run() override;

private:
    ICore* m_core = nullptr;

    QMutex m_mutex;
    QWaitCondition m_condition;

    std::atomic<bool> m_running{true};
    std::atomic<bool> m_frameRequested{false};
    std::atomic<bool> m_frameCompleted{false};

    uint32_t m_pendingInput = 0;
};
