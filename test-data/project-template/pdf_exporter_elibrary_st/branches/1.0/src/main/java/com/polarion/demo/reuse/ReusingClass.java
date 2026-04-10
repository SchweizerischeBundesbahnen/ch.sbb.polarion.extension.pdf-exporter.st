package com.polarion.demo.reuse;

import org.apache.commons.collections.primitives.ArrayIntList;
import org.apache.commons.collections.primitives.IntList;
import org.apache.commons.configuration.BaseConfiguration;
import org.apache.log4j.Logger;

public class ReusingClass {

    public void reuseCommonsPrimitives() {
        Logger log;
        IntList intList = new ArrayIntList(5);
        for(int i = 0; i < 5; i++) {
            intList.add(i);
        }
    }

    public void reuseCommonsConfiguration() {
        BaseConfiguration config = new BaseConfiguration();
        config.setProperty("throw.exception.on.missing", "false");
    }

}
