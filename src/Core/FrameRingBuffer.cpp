#include "FrameRingBuffer.h"

FrameRingBuffer::FrameRingBuffer(size_t capacity)
    : m_capacity(capacity),
    m_buffer(capacity)
{
}

void FrameRingBuffer::push(const FrameData& frame)
{
    size_t index = frame.frameNumber % m_capacity;
    m_buffer[index] = frame;
}

FrameData* FrameRingBuffer::get(uint64_t frameNumber)
{
    size_t index = frameNumber % m_capacity;

    if (m_buffer[index].frameNumber == frameNumber)
        return &m_buffer[index];

    return nullptr;
}

size_t FrameRingBuffer::capacity() const
{
    return m_capacity;
}
