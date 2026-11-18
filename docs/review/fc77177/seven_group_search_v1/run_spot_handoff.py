from run_handoffs import *

def main():
    # Keep first three holders at original tiles. Only relocate the post-opening Spot group and bring Melantha's second deployment to an actual lower-outer handoff.
    for tile,d in [([6,3],'RIGHT'),([6,4],'LEFT'),([6,5],'RIGHT')]:
        for retreat in [1967,1877]:
            deploy=retreat+2101
            edits=[change(SPOT,'DEPLOY',2341,tile=[4,5],direction='UP'),change(MEL,'RETREAT',2054,frame=retreat),change(MEL,'DEPLOY',4155,frame=deploy,tile=tile,direction=d)]
            if retreat==1877:edits +=[change(MEL,'DEPLOY',841,frame=751)]
            r=variant('SPOT_LOWER_MEL'+str(tile[1])+'_R'+str(retreat),edits,'Spot inherits lower-middle #11/#13 after original opener. Melantha returns on legal cooldown to later lower-outer intercept tile rather than middle; test observed #16/#18 contact before leak. Earlier opening Melantha is paired only when clearing roadblock4 earlier is required.')
            if r.get('observed',{}).get('complete_win'):return

if __name__=='__main__':main()
