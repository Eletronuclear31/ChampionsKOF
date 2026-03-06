#include "DummyCore.h"
#include <cstring>

bool DummyCore::initialize()
{
    m_internalCounter = 0;
    return true;
}

void DummyCore::runFrame(uint32_t inputMask)
{
    // Simulação determinística simples
    m_internalCounter += 1;
    m_internalCounter ^= inputMask;
}

void DummyCore::saveState(std::vector<uint8_t>& outState)
{
    outState.resize(sizeof(m_internalCounter));
    std::memcpy(outState.data(), &m_internalCounter, sizeof(m_internalCounter));
}

void DummyCore::loadState(const std::vector<uint8_t>& state)
{
    if (state.size() == sizeof(m_internalCounter))
    {
        std::memcpy(&m_internalCounter, state.data(), sizeof(m_internalCounter));
    }
}

uint64_t DummyCore::computeHash() const
{
    return m_internalCounter;
}
