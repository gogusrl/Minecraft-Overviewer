====================
Minecraft Overviewer
====================
By Andrew Brown

http://github.com/brownan/Minecraft-Overviewer

Generates large resolution images of a Minecraft map.

In short, this program reads in Minecraft world files and renders very large
resolution images. It performs a similar function to the existing Minecraft
Cartographer program but with a slightly different goal in mind: to generate
large resolution images such that one can zoom in and see details.

Features
========

* Renders large resolution images of your world, such that you can zoom in and
  see details

* Outputs a Google Map powered interface that is memory efficient, both in
  generating and viewing.

* Renders efficiently in parallel, using as many simultaneous processes as you
  want!

* Utilizes 2 levels of caching to speed up subsequent renderings of your world.

* Throw the output directory up on a web server to share your Minecraft world
  with everyone!

Requirements
============
This program requires:

* Python 2.6 or 2.7 <http://python.org/download/>
* PIL (Python Imaging Library) <http://www.pythonware.com/products/pil/>
* Numpy <http://scipy.org/Download>

I develop and test this on Linux, but need help testing it on Windows and Mac.
If something doesn't work, let me know.

Using the Overviewer
====================

Disclaimers
-----------
Before you dive into using this, just be aware that, for large maps, there is a
*lot* of data to parse through and process. If your world is very large, expect
the initial render to take at least an hour, possibly more. (Since minecraft
maps are practically infinite, the maximum time this could take is also
infinite!)

If you press ctrl-C, it will stop. The next run will pick up where it left off.

Once your initial render is done, subsequent renderings will be MUCH faster due
to all the caching that happens behind the scenes. Just use the same output
directory and it will only update the tiles it needs to.

There are probably some other minor glitches along the way, hopefully they will
be fixed soon. See the `Bugs`_ section below.

Running
-------
To generate a set of Google Map tiles, use the gmap.py script like this::

    python gmap.py <Path to World> <Output Directory>

The output directory will be created if it doesn't exist. This will generate a
set of image tiles for your world in the directory you choose. When it's done,
you will find an index.html file in the same directory that you can use to view
it.

Using more Cores
----------------
Adding the "-p" option will utilize more cores during processing.  This can
speed up rendering quite a bit. The default is set to the same number of cores
in your computer, but you can adjust it.

Example to run 5 worker processes in parallel::

    python gmap.py -p 5 <Path to World> <Output Directory>

Specifying the Zoom Level
-------------------------
The -z option will set the zoom level manually. Without this option, the
Overviewer will detect the smallest number of zoom levels needed to render your
entire map.

Maybe that's too much though, or maybe you have some outlier chunks that are
very far off making your map too large to render. That's where this option
comes in handy.

This will render your map with 7 zoom levels::

    python gmap.py -z 7 <Path to World> <Output Directory>

The zoom level specifies the number of tiles at the highest zoom level. A zoom
level of z will generate up to 4^z tiles (2^z by 2^z in a square). This means
each additional zoom level covers 4 times as much area as the last one. Tiles
with no content will not be rendered, but they still take a small amount of
time to process.

Viewing the Results
-------------------
The output is two things: an index.html file, and a directory hierarchy full of
images. To view your world, simply open index.html in a web browser. Internet
access is required to load the Google Maps API files, but you otherwise don't
need anything else.

You can throw these files up to a web server to let others view your map. You
do *not* need a Google Maps API key (as was the case with older versions of the
API), so just copying the directory to your web server should suffice.

Clearing the Cache
------------------
The Overviewer keeps two levels of cache: it saves each chunk rendered
individually along side your chunk files in your saved world directory, and it
keeps a hash file along side each tile in your output directory. Using these
cache files it will not re-render any image that has not changed.

If you want to clear the cache and re-render everything, run gmap.py with the
-d option::

    python gmap.py -d <Path to World> <Output Directory>

The next time your map is rendered, it will re-render every chunk. This is
useful if you've changed texture packs or want to save disk space, but
otherwise not too useful.

This is probably *not* a good idea for very large worlds, since it will take
much longer to render the next time you do so.

Crushing the Output Tiles
-------------------------
Image files taking too much disk space? Try using pngcrush. On Linux and
probably Mac, if you have pngcrush installed, this command will go and crush
all your images in the given destination. This took the total disk usage of the
render for my world from 85M to 67M.

::

    find /path/to/destination -name "*.png" -exec pngcrush {} {}.crush \; -exec mv {}.crush {} \;

If you're on Windows, I've gotten word that this command line snippet works
provided pngout is installed and on your path. Note that the % symbols will
need to be doubled up if this is in a batch file.

::

    FOR /R c:\path\to\tiles\folder %v IN (*.png) DO pngout %v /y

Bugs
====
This program has bugs. They are mostly minor things, I wouldn't have released a
completely useless program. However, there are a number of things that I want
to fix or improve.

For a current list of issues, visit
http://github.com/brownan/Minecraft-Overviewer/issues

Feel free to comment on issues, report new issues, and vote on issues that are
important to you, so I can prioritize accordingly.

An incomplete list of things I want to fix soon is:

* Rendering non-cube blocks, such as torches, flowers, mine tracks, fences,
  doors, and the like. Right now they are either not rendered at all, or
  rendered as if they were a cube, so it looks funny.

* Add lighting

* Some kind of graphical interface.

* A Windows exe for easier access for Windows users.
