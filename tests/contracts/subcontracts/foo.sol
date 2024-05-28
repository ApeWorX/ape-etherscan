// SPDX-License-Identifier: AGPL-3.0
pragma solidity ^0.8.20;

import "@bar/contracts/bar.sol";

library MyLib {
    function insert(uint value) public returns (bool) {
        return true;
    }
}

contract foo {
    function register(uint value) public {
        require(MyLib.insert(value));
    }
}

contract fooWithConstructor {
    uint public value;
    constructor(uint _value) {
        value = _value;
    }
}
