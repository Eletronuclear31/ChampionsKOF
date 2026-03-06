#include "HighPrecisionTimer.h"

HighPrecisionTimer::HighPrecisionTimer()
{
    QueryPerformanceFrequency(&m_frequency);
    QueryPerformanceCounter(&m_start);
}

void HighPrecisionTimer::reset()
{
    QueryPerformanceCounter(&m_start);
}

double HighPrecisionTimer::elapsedMilliseconds() const
{
    LARGE_INTEGER now;
    QueryPerformanceCounter(&now);

    return (double)(now.QuadPart - m_start.QuadPart) * 1000.0 / m_frequency.QuadPart;
}
