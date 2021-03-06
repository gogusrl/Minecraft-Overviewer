import multiprocessing
import itertools
import os
import os.path
import hashlib
import functools
import re
import shutil

from PIL import Image

"""
This module has routines related to generating a quadtree of tiles

"""

def iterate_base4(d):
    """Iterates over a base 4 number with d digits"""
    return itertools.product(xrange(4), repeat=d)

def catch_keyboardinterrupt(func):
    """Decorator that catches a keyboardinterrupt and raises a real exception
    so that multiprocessing will propagate it properly"""
    @functools.wraps(func)
    def newfunc(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except KeyboardInterrupt:
            print "Ctrl-C caught!"
            raise Exception("Exiting")
        except:
            import traceback
            traceback.print_exc()
            raise
    return newfunc

class QuadtreeGen(object):
    def __init__(self, worldobj, destdir, depth=None):
        """Generates a quadtree from the world given into the
        given dest directory

        worldobj is a world.WorldRenderer object that has already been processed

        If depth is given, it overrides the calculated value. Otherwise, the
        minimum depth that contains all chunks is calculated and used.

        """
        if depth is None:
            # Determine quadtree depth (midpoint is always 0,0)
            for p in xrange(15):
                # Will 2^p tiles wide and high suffice?

                # X has twice as many chunks as tiles, then halved since this is a
                # radius
                xradius = 2**p
                # Y has 4 times as many chunks as tiles, then halved since this is
                # a radius
                yradius = 2*2**p
                if xradius >= worldobj.maxcol and -xradius <= worldobj.mincol and \
                        yradius >= worldobj.maxrow and -yradius <= worldobj.minrow:
                    break
            else:
                raise ValueError("Your map is waaaay too big!")

            self.p = p
        else:
            self.p = depth
            xradius = 2**depth
            yradius = 2*2**depth

        # Make new row and column ranges
        self.mincol = -xradius
        self.maxcol = xradius
        self.minrow = -yradius
        self.maxrow = yradius

        self.world = worldobj
        self.destdir = destdir

    def write_html(self, zoomlevel):
        """Writes out index.html"""
        templatepath = os.path.join(os.path.split(__file__)[0], "template.html")

        html = open(templatepath, 'r').read()
        html = html.replace(
                "{maxzoom}", str(zoomlevel))
                
        with open(os.path.join(self.destdir, "index.html"), 'w') as output:
            output.write(html)

    def _get_cur_depth(self):
        """How deep is the quadtree currently in the destdir? This glances in
        index.html to see what maxZoom is set to.
        returns -1 if it couldn't be detected, file not found, or nothing in
        index.html matched
        """
        indexfile = os.path.join(self.destdir, "index.html")
        if not os.path.exists(indexfile):
            return -1
        matcher = re.compile(r"maxZoom:\s*(\d+)")
        p = -1
        for line in open(indexfile, "r"):
            res = matcher.search(line)
            if res:
                p = int(res.group(1))
                break
        return p

    def _increase_depth(self):
        """Moves existing tiles into place for a larger tree"""
        getpath = functools.partial(os.path.join, self.destdir, "tiles")

        # At top level of the tree:
        # quadrant 0 is now 0/3
        # 1 is now 1/2
        # 2 is now 2/1
        # 3 is now 3/0
        # then all that needs to be done is to regenerate the new top level
        for dirnum in range(4):
            newnum = (3,2,1,0)[dirnum]

            newdir = "new" + str(dirnum)
            newdirpath = getpath(newdir)

            files = [str(dirnum)+".png", str(dirnum)+".hash", str(dirnum)]
            newfiles = [str(newnum)+".png", str(newnum)+".hash", str(newnum)]

            os.mkdir(newdirpath)
            for f, newf in zip(files, newfiles):
                p = getpath(f)
                if os.path.exists(p):
                    os.rename(p, getpath(newdir, newf))
            os.rename(newdirpath, getpath(str(dirnum)))

    def _decrease_depth(self):
        """If the map size decreases, or perhaps the user has a depth override
        in effect, re-arrange existing tiles for a smaller tree"""
        getpath = functools.partial(os.path.join, self.destdir, "tiles")

        # quadrant 0/3 goes to 0
        # 1/2 goes to 1
        # 2/1 goes to 2
        # 3/0 goes to 3
        # Just worry about the directories here, the files at the top two
        # levels are cheap enough to replace
        if os.path.exists(getpath("0", "3")):
            os.rename(getpath("0", "3"), getpath("new0"))
            shutil.rmtree(getpath("0"))
            os.rename(getpath("new0"), getpath("0"))

        if os.path.exists(getpath("1", "2")):
            os.rename(getpath("1", "2"), getpath("new1"))
            shutil.rmtree(getpath("1"))
            os.rename(getpath("new1"), getpath("1"))

        if os.path.exists(getpath("2", "1")):
            os.rename(getpath("2", "1"), getpath("new2"))
            shutil.rmtree(getpath("2"))
            os.rename(getpath("new2"), getpath("2"))

        if os.path.exists(getpath("3", "0")):
            os.rename(getpath("3", "0"), getpath("new3"))
            shutil.rmtree(getpath("3"))
            os.rename(getpath("new3"), getpath("3"))

    def go(self, procs):
        """Renders all tiles"""

        # Make the destination dir
        if not os.path.exists(self.destdir):
            os.mkdir(self.destdir)

        curdepth = self._get_cur_depth()
        if curdepth != -1:
            if self.p > curdepth:
                print "Your map seemes to have expanded beyond its previous bounds."
                print "Doing some tile re-arrangements... just a sec..."
                for _ in xrange(self.p-curdepth):
                    self._increase_depth()
            elif self.p < curdepth:
                print "Your map seems to have shrunk. Re-arranging tiles, just a sec..."
                for _ in xrange(curdepth - self.p):
                    self._decrease_depth()

        # Create a pool
        pool = multiprocessing.Pool(processes=procs)

        # Render the highest level of tiles from the chunks
        print "Computing the tile ranges and starting tile processers for inner-most tiles..."
        print "This takes the longest. The other levels will go quicker"
        results = []
        for path in iterate_base4(self.p):
            # Get the range for this tile
            colstart, rowstart = self._get_range_by_path(path)
            colend = colstart + 2
            rowend = rowstart + 4

            # This image is rendered at:
            dest = os.path.join(self.destdir, "tiles", *(str(x) for x in path))

            # And uses these chunks
            tilechunks = self._get_chunks_in_range(colstart, colend, rowstart,
                    rowend)

            # Put this in the pool
            # (even if tilechunks is empty, render_worldtile will delete
            # existing images if appropriate)
            results.append(
                    pool.apply_async(func=render_worldtile, args=
                        (tilechunks, colstart, colend, rowstart, rowend, dest)
                        )
                    )

        self.write_html(self.p)

        # Wait for all results to finish
        print "Rendering inner most zoom level tiles now!"
        for i, result in enumerate(results):
            # get() instead of wait() so we can see errors
            result.get()
            if i > 0 and (i % 100 == 0 or 100 % i == 0):
                print "{0}/{1} tiles complete on level 1/{2}".format(
                        i, len(results), self.p)
        print "Done"

        # Now do the other layers
        for zoom in xrange(self.p-1, 0, -1):
            level = self.p - zoom + 1
            print "Starting level", level
            results = []
            for path in iterate_base4(zoom):
                # This image is rendered at:
                dest = os.path.join(self.destdir, "tiles", *(str(x) for x in path[:-1]))
                name = str(path[-1])

                results.append(
                        pool.apply_async(func=render_innertile, args=
                            (dest, name)
                            )
                        )

            for i, result in enumerate(results):
                # get() instead of wait() so we can see errors
                result.get()
                if i > 0 and (i % 100 == 0 or 100 % i == 0):
                    print "{0}/{1} tiles complete for level {2}/{3}".format(
                            i, len(results), level, self.p)
            print "Done"

        # Do the final one right here:
        render_innertile(os.path.join(self.destdir, "tiles"), "base")

        pool.close()
        pool.join()

    def _get_range_by_path(self, path):
        """Returns the x, y chunk coordinates of this tile"""
        x, y = self.mincol, self.minrow
        
        xsize = self.maxcol
        ysize = self.maxrow

        for p in path:
            if p in (1, 3):
                x += xsize
            if p in (2, 3):
                y += ysize
            xsize //= 2
            ysize //= 2

        return x, y

    def _get_chunks_in_range(self, colstart, colend, rowstart, rowend):
        """Get chunks that are relevant to the tile rendering function that's
        rendering that range"""
        chunklist = []
        for row in xrange(rowstart-16, rowend+1):
            for col in xrange(colstart, colend+1):
                c = self.world.chunkmap.get((col, row), None)
                if c:
                    chunklist.append((col, row, c))
        return chunklist

@catch_keyboardinterrupt
def render_innertile(dest, name):
    """
    Renders a tile at os.path.join(dest, name)+".png" by taking tiles from
    os.path.join(dest, name, "{0,1,2,3}.png")
    """
    imgpath = os.path.join(dest, name) + ".png"
    hashpath = os.path.join(dest, name) + ".hash"

    if name == "base":
        q0path = os.path.join(dest, "0.png")
        q1path = os.path.join(dest, "1.png")
        q2path = os.path.join(dest, "2.png")
        q3path = os.path.join(dest, "3.png")
        q0hash = os.path.join(dest, "0.hash")
        q1hash = os.path.join(dest, "1.hash")
        q2hash = os.path.join(dest, "2.hash")
        q3hash = os.path.join(dest, "3.hash")
    else:
        q0path = os.path.join(dest, name, "0.png")
        q1path = os.path.join(dest, name, "1.png")
        q2path = os.path.join(dest, name, "2.png")
        q3path = os.path.join(dest, name, "3.png")
        q0hash = os.path.join(dest, name, "0.hash")
        q1hash = os.path.join(dest, name, "1.hash")
        q2hash = os.path.join(dest, name, "2.hash")
        q3hash = os.path.join(dest, name, "3.hash")

    # Check which ones exist
    if not os.path.exists(q0hash):
        q0path = None
        q0hash = None
    if not os.path.exists(q1hash):
        q1path = None
        q1hash = None
    if not os.path.exists(q2hash):
        q2path = None
        q2hash = None
    if not os.path.exists(q3hash):
        q3path = None
        q3hash = None

    # do they all not exist?
    if not (q0path or q1path or q2path or q3path):
        if os.path.exists(imgpath):
            os.unlink(imgpath)
        if os.path.exists(hashpath):
            os.unlink(hashpath)
        return
    
    # Now check the hashes
    hasher = hashlib.md5()
    if q0hash:
        hasher.update(open(q0hash, "rb").read())
    if q1hash:
        hasher.update(open(q1hash, "rb").read())
    if q2hash:
        hasher.update(open(q2hash, "rb").read())
    if q3hash:
        hasher.update(open(q3hash, "rb").read())
    if os.path.exists(hashpath):
        oldhash = open(hashpath, "rb").read()
    else:
        oldhash = None
    newhash = hasher.digest()

    if newhash == oldhash:
        # Nothing to do
        return

    # Create the actual image now
    img = Image.new("RGBA", (384, 384), (38,92,255,0))

    if q0path:
        quad0 = Image.open(q0path).resize((192,192), Image.ANTIALIAS)
        img.paste(quad0, (0,0))
    if q1path:
        quad1 = Image.open(q1path).resize((192,192), Image.ANTIALIAS)
        img.paste(quad1, (192,0))
    if q2path:
        quad2 = Image.open(q2path).resize((192,192), Image.ANTIALIAS)
        img.paste(quad2, (0, 192))
    if q3path:
        quad3 = Image.open(q3path).resize((192,192), Image.ANTIALIAS)
        img.paste(quad3, (192, 192))

    # Save it
    img.save(imgpath)
    with open(hashpath, "wb") as hashout:
        hashout.write(newhash)


@catch_keyboardinterrupt
def render_worldtile(chunks, colstart, colend, rowstart, rowend, path):
    """Renders just the specified chunks into a tile and save it. Unlike usual
    python conventions, rowend and colend are inclusive. Additionally, the
    chunks around the edges are half-way cut off (so that neighboring tiles
    will render the other half)

    chunks is a list of (col, row, filename) of chunk images that are relevant
    to this call

    The image is saved to path+".png" and a hash is saved to path+".hash"

    If there are no chunks, this tile is not saved (if it already exists, it is
    deleted)

    If the hash file already exists, it is checked against the hash of each chunk.

    Standard tile size has colend-colstart=2 and rowend-rowstart=4

    There is no return value
    """
    # width of one chunk is 384. Each column is half a chunk wide. The total
    # width is (384 + 192*(numcols-1)) since the first column contributes full
    # width, and each additional one contributes half since they're staggered.
    # However, since we want to cut off half a chunk at each end (384 less
    # pixels) and since (colend - colstart + 1) is the number of columns
    # inclusive, the equation simplifies to:
    width = 192 * (colend - colstart)
    # Same deal with height
    height = 96 * (rowend - rowstart)

    # The standard tile size is 3 columns by 5 rows, which works out to 384x384
    # pixels for 8 total chunks. (Since the chunks are staggered but the grid
    # is not, some grid coordinates do not address chunks) The two chunks on
    # the middle column are shown in full, the two chunks in the middle row are
    # half cut off, and the four remaining chunks are one quarter shown.
    # The above example with cols 0-3 and rows 0-4 has the chunks arranged like this:
    #   0,0         2,0
    #         1,1
    #   0,2         2,2
    #         1,3
    #   0,4         2,4

    # Due to how the tiles fit together, we may need to render chunks way above
    # this (since very few chunks actually touch the top of the sky, some tiles
    # way above this one are possibly visible in this tile). Render them
    # anyways just in case). "chunks" should include up to rowstart-16

    # Before we render any tiles, check the hash of each image in this tile to
    # see if it's changed.
    hashpath = path + ".hash"
    imgpath = path + ".png"

    if not chunks:
        # No chunks were found in this tile
        if os.path.exists(imgpath):
            os.unlink(imgpath)
        if os.path.exists(hashpath):
            os.unlink(hashpath)
        return None

    # Create the directory if not exists
    dirdest = os.path.dirname(path)
    if not os.path.exists(dirdest):
        try:
            os.makedirs(dirdest)
        except OSError, e:
            # Ignore errno EEXIST: file exists. Since this is multithreaded,
            # two processes could conceivably try and create the same directory
            # at the same time.
            import errno
            if e.errno != errno.EEXIST:
                raise

    imghash = hashlib.md5()
    for col, row, chunkfile in chunks:
        # Get the hash of this image and add it to our hash for this tile
        imghash.update(
                os.path.basename(chunkfile).split(".")[4]
                )
    digest = imghash.digest()

    if os.path.exists(hashpath):
        oldhash = open(hashpath, 'rb').read()
    else:
        oldhash = None

    if digest == oldhash:
        # All the chunks for this tile have not changed according to the hash
        return

    # Compile this image
    tileimg = Image.new("RGBA", (width, height), (38,92,255,0))

    # col colstart will get drawn on the image starting at x coordinates -(384/2)
    # row rowstart will get drawn on the image starting at y coordinates -(192/2)
    for col, row, chunkfile in chunks:
        try:
            chunkimg = Image.open(chunkfile)
        except IOError, e:
            print "Error opening file", chunkfile
            print "Attempting to re-generate it..."
            os.unlink(chunkfile)
            # Do some string manipulation to determine what the chunk file is
            # that goes with this image. Then call chunk.render_and_save
            dirname, imagename = os.path.split(chunkfile)
            parts = imagename.split(".")
            datafile = "c.{0}.{1}.dat".format(parts[1],parts[2])
            #print "Chunk came from data file", datafile
            # XXX Don't forget to set cave mode here when it gets implemented!
            chunk.render_and_save(os.path.join(dirname, datafile), False)
            chunkimg = Image.open(chunkfile)
            print "Success"

        xpos = -192 + (col-colstart)*192
        ypos = -96 + (row-rowstart)*96

        tileimg.paste(chunkimg.convert("RGB"), (xpos, ypos), chunkimg)

    # Save them
    tileimg.save(imgpath)
    with open(hashpath, "wb") as hashout:
        hashout.write(digest)

