#pragma once

#include <cstdint>

class FrameHash
{
public:
    static uint64_t compute(uint64_t frameNumber, uint32_t inputMask);
};
