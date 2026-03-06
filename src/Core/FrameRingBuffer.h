#pragma once

#include "FrameData.h"
#include <vector>
#include <cstddef>

class FrameRingBuffer
{
public:
    explicit FrameRingBuffer(size_t capacity);

    void push(const FrameData& frame);
    FrameData* get(uint64_t frameNumber);

    size_t capacity() const;

private:
    size_t m_capacity;
    std::vector<FrameData> m_buffer;
};
