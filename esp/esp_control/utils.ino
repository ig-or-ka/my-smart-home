#include "utils.h"

void SplitLine(std::vector<String>& res, String line, String sep){
    int end_index = line.indexOf(sep);
    while(end_index != -1){
        auto sub = line.substring(0, end_index);

        res.push_back(sub);

        line = line.substring(end_index+sep.length(), line.length());

        end_index = line.indexOf(sep);
    }

    res.push_back(line);
}