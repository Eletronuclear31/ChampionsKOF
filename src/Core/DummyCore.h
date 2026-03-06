#pragma once

#include "ICore.h"
#include <cstdint>

class DummyCore : public ICore
{
public:
    bool initialize() override;

    void runFrame(uint32_t inputMask) override;

    void saveState(std::vector<uint8_t>& outState) override;
    void loadState(const std::vector<uint8_t>& state) override;

    uint64_t computeHash() const override;

private:
    uint64_t m_internalCounter = 0;
};
