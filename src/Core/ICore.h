#pragma once

#include <cstdint>
#include <vector>

class ICore
{
public:
    virtual ~ICore() = default;

    virtual bool initialize() = 0;

    virtual void runFrame(uint32_t inputMask) = 0;

    virtual void saveState(std::vector<uint8_t>& outState) = 0;
    virtual void loadState(const std::vector<uint8_t>& state) = 0;

    virtual uint64_t computeHash() const = 0;
};
