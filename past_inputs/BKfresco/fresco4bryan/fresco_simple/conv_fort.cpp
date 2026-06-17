// -------------------------------------------------------------------
//
// This file was originally composed by Brian Roeder, and is being 
// used and manipulated by Kenneth Hanselman as of 22 March 2017.
// Original header follows.
//
// conv_fort.cpp
//
// Written : 18 July 2007 by Brian Roeder, LPC Caen
// email : roeder@lpccaen.in2p3.fr
//
// Description : A C++ program that reads the Fresco DWBA output file
//              "fort.16" and converts it into a text file for use with
//               xmgrace or root. Setup only to read differential cross
//              sections and not the analyzing powers.
//
// --------------------------------------------------------------------

#include <iostream>
#include <iomanip>
#include <fstream>
#include <cstring>
#include <cctype>
#include <string>
#include <stdio.h>

using namespace std;

int main(int argc, char* argv[]){

  char NewFileName[51];

  ifstream infile;
  infile.open("fort.16");

  string dummy;

  while (dummy != "projectile")
    infile >> dummy;

  string theta = "";
  string sigma = "";

  int state_counter = 0;
    
  ofstream outfile;

  while (!(infile.eof())) {

    char outfile_name[100];

    char state_number[100];
    sprintf(state_number, "%i", state_counter);

    theta = "";
    sigma = "";

    switch (state_counter) {
    case 0:
      outfile.open("plotFiles/elastic.txt");
      break;
    default:
      strcpy(outfile_name,"plotFiles/state");
      strcat(outfile_name,state_number);
      strcat(outfile_name,".txt");
      outfile.open(outfile_name);
      break;
    }

    while (theta != "END") {

      infile >> theta >> sigma;
      
      if (theta != "END")
	outfile << theta << " " << sigma << endl;

    }

    outfile.close();

    state_counter++;

    dummy = "";

    if (!(infile.eof()))
      while (dummy != "projectile")
	infile >> dummy;

  }

  return 0;

}
