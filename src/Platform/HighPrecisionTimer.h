#pragma once

#include <windows.h>

class HighPrecisionTimer
{
public:
    HighPrecisionTimer();

    void reset();
    double elapsedMilliseconds() const;

private:
    LARGE_INTEGER m_frequency;
    LARGE_INTEGER m_start;
};
